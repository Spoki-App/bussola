import json
import secrets
import threading
from collections.abc import Generator
from contextlib import contextmanager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, cast

from bussola.ai.base import AiCancelledError, ToolRunner, json_object

SERVER_NAME = "bussola"
SERVER_VERSION = "1"
LOOPBACK = "127.0.0.1"
MAX_BODY_BYTES = 1_000_000
METHOD_NOT_FOUND = -32601
INVALID_REQUEST = -32600
WORKER_NAME = "bussola-mcp"


@contextmanager
def serve_tools(tools: ToolRunner) -> Generator[str]:
    path = f"/mcp/{secrets.token_urlsafe(24)}"
    server = ThreadingHTTPServer((LOOPBACK, 0), _handler(tools, path))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, name=WORKER_NAME, daemon=True)
    thread.start()
    try:
        yield f"http://{LOOPBACK}:{server.server_address[1]}{path}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _handler(tools: ToolRunner, path: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            if self.path != path:
                self._reply(HTTPStatus.NOT_FOUND)
                return
            if not 0 < length <= MAX_BODY_BYTES:
                self._reply(HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                return
            try:
                message = json.loads(self.rfile.read(length))
            except json.JSONDecodeError:
                self._reply(HTTPStatus.BAD_REQUEST)
                return
            items: list[Any] = cast(list[Any], message) if isinstance(message, list) else [message]
            answers = [answer for item in items if (answer := _answer(tools, item)) is not None]
            if not answers:
                self._reply(HTTPStatus.ACCEPTED)
                return
            self._reply(HTTPStatus.OK, answers if isinstance(message, list) else answers[0])

        def do_GET(self) -> None:
            self._reply(HTTPStatus.METHOD_NOT_ALLOWED)

        def do_DELETE(self) -> None:
            self._reply(HTTPStatus.OK if self.path == path else HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            pass

        def _reply(self, status: HTTPStatus, body: Any = None) -> None:
            data = b"" if body is None else json.dumps(body).encode()
            self.send_response(status)
            if body is not None:
                self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return Handler


def _answer(tools: ToolRunner, item: Any) -> dict[str, Any] | None:
    message = json_object(item)
    if message is None:
        return {"jsonrpc": "2.0", "id": None, "error": {"code": INVALID_REQUEST, "message": "Expected a JSON-RPC object"}}
    if "id" not in message:
        return None
    params = json_object(message.get("params")) or {}
    match message.get("method"):
        case "initialize":
            result: dict[str, Any] = {
                "protocolVersion": params.get("protocolVersion"),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            }
        case "tools/list":
            result = {"tools": [{"name": tool.name, "description": tool.description, "inputSchema": tool.schema} for tool in tools.definitions]}
        case "tools/call":
            result = _call(tools, params)
        case "ping":
            result = {}
        case method:
            return {"jsonrpc": "2.0", "id": message["id"], "error": {"code": METHOD_NOT_FOUND, "message": f"Unknown method {method}"}}
    return {"jsonrpc": "2.0", "id": message["id"], "result": result}


def _call(tools: ToolRunner, params: dict[str, Any]) -> dict[str, Any]:
    try:
        outcome = tools.call(str(params.get("name")), json_object(params.get("arguments")) or {})
    except AiCancelledError:
        return {"content": [{"type": "text", "text": "The review was cancelled."}], "isError": True}
    return {"content": [{"type": "text", "text": outcome.text}], "isError": outcome.error}
