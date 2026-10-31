import contextlib
import http.client
import ipaddress
import json
import socket
import ssl
import threading
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from typing import Any

from bussola.ai.base import MAX_ERROR_LENGTH, AiProviderError, Cancellation, json_object, run_cancellable

SOCKET_GRACE_SECONDS = 5.0
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
LOOPBACK_NAME = "localhost"

type ConnectionClass = Callable[..., http.client.HTTPConnection]


class _Connections:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._open: list[http.client.HTTPConnection] = []

    def tracked(self, connection_class: ConnectionClass) -> ConnectionClass:
        def build(*args: Any, **kwargs: Any) -> http.client.HTTPConnection:
            connection = connection_class(*args, **kwargs)
            with self._lock:
                self._open.append(connection)
            return connection

        return build

    def close(self) -> None:
        with self._lock:
            connections = list(self._open)
        for connection in connections:
            with contextlib.suppress(OSError):
                if connection.sock is not None:
                    connection.sock.shutdown(socket.SHUT_RDWR)
            connection.close()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class _TrackedHttpHandler(urllib.request.HTTPHandler):
    def __init__(self, connections: _Connections) -> None:
        super().__init__()
        self._connections = connections

    def http_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        return self.do_open(self._connections.tracked(http.client.HTTPConnection), req)


class _TrackedHttpsHandler(urllib.request.HTTPSHandler):
    def __init__(self, connections: _Connections) -> None:
        super().__init__()
        self._connections = connections
        self._ssl_context = ssl.create_default_context()

    def https_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        return self.do_open(self._connections.tracked(http.client.HTTPSConnection), req, context=self._ssl_context)


def bypasses_proxy(url: str) -> bool:
    host = (urllib.parse.urlsplit(url).hostname or "").rstrip(".")
    if host == LOOPBACK_NAME or host.endswith(f".{LOOPBACK_NAME}"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _opener(url: str, connections: _Connections) -> urllib.request.OpenerDirector:
    handlers: list[urllib.request.BaseHandler] = [_NoRedirect(), _TrackedHttpHandler(connections), _TrackedHttpsHandler(connections)]
    if bypasses_proxy(url):
        handlers.append(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener(*handlers)


def post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float, cancellation: Cancellation) -> dict[str, Any]:
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **headers}, method="POST")
    connections = _Connections()
    opener = _opener(url, connections)

    def send() -> bytes:
        with opener.open(request, timeout=timeout + SOCKET_GRACE_SECONDS) as response:
            return response.read(MAX_RESPONSE_BYTES + 1)

    try:
        body = run_cancellable(send, cancellation, timeout, abort=connections.close)
    except urllib.error.HTTPError as error:
        raise AiProviderError(f"{url} answered HTTP {error.code}: {_error_detail(error)}") from error
    except urllib.error.URLError as error:
        raise AiProviderError(f"Cannot reach {url}: {error.reason}") from error
    except (http.client.HTTPException, OSError) as error:
        raise AiProviderError(f"The connection to {url} failed: {error or type(error).__name__}") from error
    except ValueError as error:
        raise AiProviderError(f"The request to {url} could not be sent: {error}") from error
    if len(body) > MAX_RESPONSE_BYTES:
        raise AiProviderError(f"{url} answered with more than {MAX_RESPONSE_BYTES // (1024 * 1024)} MB")
    try:
        decoded = json_object(json.loads(body))
    except ValueError as error:
        raise AiProviderError(f"{url} did not answer with JSON") from error
    if decoded is None:
        raise AiProviderError(f"{url} answered with unexpected JSON")
    return decoded


def _error_detail(error: urllib.error.HTTPError) -> str:
    try:
        text = error.read().decode(errors="replace")
    except (http.client.HTTPException, OSError):
        text = ""
    try:
        payload = json_object(json.loads(text)) or {}
    except ValueError:
        payload = {}
    message = (json_object(payload.get("error")) or payload).get("message")
    return str(message or text or error.reason)[:MAX_ERROR_LENGTH]
