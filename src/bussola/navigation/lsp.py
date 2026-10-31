import json
import os
import subprocess
import threading
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any, Self, cast
from urllib.parse import unquote, urlparse
from urllib.request import url2pathname

from bussola.navigation.specs import ServerSpec

INITIALIZE_TIMEOUT_SECONDS = 30.0
REQUEST_TIMEOUT_SECONDS = 5.0
SHUTDOWN_TIMEOUT_SECONDS = 1.0
CONTENT_LENGTH = b"content-length"
FILE_SCHEME = "file"
CONFIGURATION_REQUEST = "workspace/configuration"


class LanguageServerError(Exception):
    pass


@dataclass(frozen=True)
class ServerLocation:
    path: str
    row: int
    character: int


class LanguageServerClient:
    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        if process.stdin is None or process.stdout is None:
            raise LanguageServerError("The language server has no pipes")
        self._process = process
        self._stdin: IO[bytes] = process.stdin
        self._stdout: IO[bytes] = process.stdout
        self._write_lock = threading.Lock()
        self._pending: dict[int, Future[Any]] = {}
        self._next_id = 0
        self._closed = False
        threading.Thread(target=self._read_loop, name="bussola-language-server", daemon=True).start()

    @classmethod
    def start(cls, command: list[str], cwd: Path, environment: dict[str, str]) -> Self:
        try:
            process = subprocess.Popen(
                command, cwd=cwd, env={**os.environ, **environment}, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
            )
        except OSError as error:
            raise LanguageServerError(f"Could not start {command[0]}") from error
        return cls(process)

    def request(self, method: str, params: Any, timeout: float) -> Any:
        future: Future[Any] = Future()
        with self._write_lock:
            if self._closed:
                raise LanguageServerError("The language server has exited")
            self._next_id += 1
            request_id = self._next_id
            self._pending[request_id] = future
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        try:
            return future.result(timeout)
        except FutureTimeout as error:
            raise LanguageServerError(f"{method} timed out") from error
        finally:
            with self._write_lock:
                self._pending.pop(request_id, None)

    def notify(self, method: str, params: Any) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def close(self) -> None:
        try:
            self.request("shutdown", None, SHUTDOWN_TIMEOUT_SECONDS)
            self.notify("exit", None)
        except LanguageServerError:
            pass
        try:
            self._process.wait(SHUTDOWN_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()

    def _send(self, message: dict[str, Any]) -> None:
        body = json.dumps(message).encode()
        try:
            with self._write_lock:
                self._stdin.write(b"Content-Length: %d\r\n\r\n%s" % (len(body), body))
                self._stdin.flush()
        except (OSError, ValueError) as error:
            raise LanguageServerError("The language server is not reading its input") from error

    def _read_loop(self) -> None:
        try:
            while (message := self._read_message()) is not None:
                self._dispatch(message)
        except (OSError, ValueError):
            pass
        with self._write_lock:
            self._closed = True
            pending = list(self._pending.values())
        for future in pending:
            if not future.done():
                future.set_exception(LanguageServerError("The language server has exited"))

    def _read_message(self) -> dict[str, Any] | None:
        length = None
        while True:
            line = self._stdout.readline()
            if not line:
                return None
            if not line.strip():
                break
            name, _, value = line.partition(b":")
            if name.strip().lower() == CONTENT_LENGTH:
                length = int(value.strip())
        if length is None:
            raise ValueError("Language server message without Content-Length")
        return _as_object(json.loads(self._stdout.read(length)))

    def _dispatch(self, message: dict[str, Any]) -> None:
        method = message.get("method")
        if method is not None and "id" in message:
            self._answer(message["id"], method, message.get("params"))
            return
        with self._write_lock:
            future = self._pending.get(message.get("id", -1))
        if future is None or future.done():
            return
        if "error" in message:
            future.set_exception(LanguageServerError(str(message["error"])))
        else:
            future.set_result(message.get("result"))

    def _answer(self, request_id: Any, method: str, params: Any) -> None:
        items = _as_object(params).get("items")
        result = [None] * len(cast(list[Any], items)) if method == CONFIGURATION_REQUEST and isinstance(items, list) else None
        try:
            self._send({"jsonrpc": "2.0", "id": request_id, "result": result})
        except LanguageServerError:
            return


class LanguageServerSession:
    def __init__(self, client: LanguageServerClient, root: Path, language_ids: dict[str, str]) -> None:
        self._client = client
        self._root = root
        self._language_ids = language_ids
        self._opened: set[str] = set()
        self._lock = threading.Lock()

    @classmethod
    def open(cls, command: list[str], root: Path, spec: ServerSpec) -> Self:
        client = LanguageServerClient.start(command, root, spec.environment)
        try:
            client.request("initialize", _initialize_params(root, spec.initialization_options), INITIALIZE_TIMEOUT_SECONDS)
            client.notify("initialized", {})
        except LanguageServerError:
            client.close()
            raise
        return cls(client, root, spec.language_ids)

    def definitions(self, path: str, row: int, character: int) -> list[ServerLocation]:
        return self._locate("textDocument/definition", path, row, character, {})

    def references(self, path: str, row: int, character: int) -> list[ServerLocation]:
        return self._locate("textDocument/references", path, row, character, {"context": {"includeDeclaration": False}})

    def close(self) -> None:
        self._client.close()

    def _locate(self, method: str, path: str, row: int, character: int, extra: dict[str, Any]) -> list[ServerLocation]:
        self._open(path)
        params = {"textDocument": {"uri": self._uri(path)}, "position": {"line": row, "character": character}, **extra}
        result = self._client.request(method, params, REQUEST_TIMEOUT_SECONDS)
        items = cast(list[Any], result) if isinstance(result, list) else [result]
        return [location for item in items if (location := self._location(_as_object(item))) is not None]

    def _open(self, path: str) -> None:
        with self._lock:
            if path in self._opened:
                return
            self._opened.add(path)
        text = (self._root / path).read_text(errors="replace")
        language_id = self._language_ids.get(Path(path).suffix.lower(), "")
        self._client.notify("textDocument/didOpen", {"textDocument": {"uri": self._uri(path), "languageId": language_id, "version": 1, "text": text}})

    def _uri(self, path: str) -> str:
        return (self._root / path).as_uri()

    def _location(self, item: dict[str, Any]) -> ServerLocation | None:
        uri = item.get("targetUri", item.get("uri"))
        start = _as_object(_as_object(item.get("targetSelectionRange", item.get("range"))).get("start"))
        path = self._relative(uri) if isinstance(uri, str) else None
        line, character = start.get("line"), start.get("character")
        if path is None or not isinstance(line, int) or not isinstance(character, int):
            return None
        return ServerLocation(path, line, character)

    def _relative(self, uri: str) -> str | None:
        parsed = urlparse(uri)
        if parsed.scheme != FILE_SCHEME:
            return None
        resolved = Path(url2pathname(unquote(parsed.path))).resolve()
        if not resolved.is_relative_to(self._root):
            return None
        return resolved.relative_to(self._root).as_posix()


def _as_object(value: Any) -> dict[str, Any]:
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _initialize_params(root: Path, options: dict[str, Any]) -> dict[str, Any]:
    return {
        "processId": os.getpid(),
        "initializationOptions": options,
        "rootUri": root.as_uri(),
        "rootPath": str(root),
        "workspaceFolders": [{"uri": root.as_uri(), "name": root.name}],
        "capabilities": {
            "textDocument": {"definition": {"linkSupport": True}, "references": {}, "synchronization": {"didSave": False}},
            "workspace": {"configuration": True, "workspaceFolders": True},
        },
    }
