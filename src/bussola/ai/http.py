import contextlib
import datetime
import email.utils
import errno
import functools
import http.client
import ipaddress
import json
import math
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from bussola.ai.base import (
    MAX_ERROR_LENGTH,
    AiProviderError,
    AiRejectedError,
    AiTimeoutError,
    AiUnreachableError,
    Cancellation,
    json_object,
    run_cancellable,
    timed_out,
)

SOCKET_GRACE_SECONDS = 5.0
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
MAX_ERROR_BODY_BYTES = 64 * 1024
REJECTING_STATUSES = frozenset({401, 403, 429})
TOO_MANY_REQUESTS = 429
FIRST_SERVER_ERROR = 500
MAX_ATTEMPTS = 3
RETRY_BASE_SECONDS = 1.0
UNREACHABLE_ERRNOS = frozenset({errno.ENETUNREACH, errno.EHOSTUNREACH})
LOOPBACK_NAME = "localhost"


class _Connections:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._open: list[http.client.HTTPConnection] = []
        self._closed = False

    def check_open(self) -> None:
        if self._closed:
            raise ConnectionAbortedError("The request was stopped")

    def register(self, connection: http.client.HTTPConnection) -> None:
        with self._lock:
            if not self._closed:
                self._open.append(connection)
                return
        connection.close()
        raise ConnectionAbortedError("The request was stopped")

    def close(self) -> None:
        with self._lock:
            self._closed = True
            connections = list(self._open)
        for connection in connections:
            with contextlib.suppress(OSError):
                if connection.sock is not None:
                    connection.sock.shutdown(socket.SHUT_RDWR)
            connection.close()


class _GuardedHttpConnection(http.client.HTTPConnection):
    def __init__(self, *args: Any, tracker: _Connections, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._tracker = tracker

    def connect(self) -> None:
        self._tracker.check_open()
        super().connect()
        self._tracker.register(self)


class _GuardedHttpsConnection(http.client.HTTPSConnection):
    def __init__(self, *args: Any, tracker: _Connections, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._tracker = tracker

    def connect(self) -> None:
        self._tracker.check_open()
        super().connect()
        self._tracker.register(self)


class _HttpStatusError(Exception):
    def __init__(self, code: int, detail: str, retry_after: float | None) -> None:
        super().__init__(code, detail)
        self.code = code
        self.detail = detail
        self.retry_after = retry_after


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class _TrackedHttpHandler(urllib.request.HTTPHandler):
    def __init__(self, connections: _Connections) -> None:
        super().__init__()
        self._connections = connections

    def http_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        return self.do_open(functools.partial(_GuardedHttpConnection, tracker=self._connections), req)


class _TrackedHttpsHandler(urllib.request.HTTPSHandler):
    def __init__(self, connections: _Connections) -> None:
        super().__init__(context=_ssl_context())
        self._connections = connections

    def https_open(self, req: urllib.request.Request) -> http.client.HTTPResponse:
        return self.do_open(functools.partial(_GuardedHttpsConnection, tracker=self._connections), req, context=_ssl_context())


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
    data = json.dumps(payload).encode()
    deadline = time.monotonic() + timeout
    attempt = 0
    while True:
        attempt += 1
        try:
            request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **headers}, method="POST")
            body = _send(request, max(deadline - time.monotonic(), 0.0), cancellation)
        except AiTimeoutError as error:
            raise timed_out(timeout) from error
        except _HttpStatusError as error:
            pause = error.retry_after if error.retry_after is not None else RETRY_BASE_SECONDS * attempt
            retryable = error.code == TOO_MANY_REQUESTS or error.code >= FIRST_SERVER_ERROR
            if not retryable or attempt == MAX_ATTEMPTS or time.monotonic() + pause >= deadline:
                failure = AiRejectedError if error.code in REJECTING_STATUSES else AiProviderError
                raise failure(f"{url} answered HTTP {error.code}: {error.detail}") from error
            cancellation.sleep(pause)
            continue
        return _decode(url, body)


def _send(request: urllib.request.Request, timeout: float, cancellation: Cancellation) -> bytes:
    url = request.full_url
    connections = _Connections()
    opener = _opener(url, connections)

    def send() -> bytes:
        try:
            with opener.open(request, timeout=timeout + SOCKET_GRACE_SECONDS) as response:
                return response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            with error:
                raise _HttpStatusError(error.code, _error_detail(error), _retry_after(error)) from error

    try:
        return run_cancellable(send, cancellation, timeout, abort=connections.close)
    except urllib.error.URLError as error:
        failure = AiUnreachableError if _unreachable(error.reason) else AiProviderError
        raise failure(f"Cannot reach {url}: {error.reason}") from error
    except (http.client.HTTPException, OSError) as error:
        raise AiProviderError(f"The connection to {url} failed: {error or type(error).__name__}") from error
    except ValueError as error:
        raise AiProviderError(f"The request to {url} could not be sent: {error}") from error


def _decode(url: str, body: bytes) -> dict[str, Any]:
    if len(body) > MAX_RESPONSE_BYTES:
        raise AiProviderError(f"{url} answered with more than {MAX_RESPONSE_BYTES // (1024 * 1024)} MB")
    try:
        decoded = json_object(json.loads(body))
    except (ValueError, RecursionError) as error:
        raise AiProviderError(f"{url} did not answer with JSON") from error
    if decoded is None:
        raise AiProviderError(f"{url} answered with unexpected JSON")
    return decoded


def _retry_after(error: urllib.error.HTTPError) -> float | None:
    value = error.headers.get("retry-after") if error.headers else None
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        seconds = _seconds_until(value)
    return max(seconds, 0.0) if seconds is not None and math.isfinite(seconds) else None


def _seconds_until(http_date: str) -> float | None:
    try:
        moment = email.utils.parsedate_to_datetime(http_date)
    except (TypeError, ValueError):
        return None
    return (moment - datetime.datetime.now(datetime.UTC)).total_seconds() if moment.tzinfo else None


def _unreachable(reason: object) -> bool:
    return isinstance(reason, ConnectionRefusedError | socket.gaierror) or getattr(reason, "errno", None) in UNREACHABLE_ERRNOS


@functools.cache
def _ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context()


def _error_detail(error: urllib.error.HTTPError) -> str:
    try:
        text = error.read(MAX_ERROR_BODY_BYTES).decode(errors="replace")
    except (http.client.HTTPException, OSError):
        text = ""
    try:
        payload = json_object(json.loads(text)) or {}
    except ValueError:
        payload = {}
    message = (json_object(payload.get("error")) or payload).get("message")
    return str(message or text or error.reason)[:MAX_ERROR_LENGTH]
