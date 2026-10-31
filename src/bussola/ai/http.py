import http.client
import ipaddress
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from bussola.ai.base import MAX_ERROR_LENGTH, AiProviderError, Cancellation, json_object, run_cancellable

SOCKET_GRACE_SECONDS = 5.0
MAX_RESPONSE_BYTES = 10 * 1024 * 1024
LOCAL_HOSTS = frozenset({"localhost"})


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


OPENER = urllib.request.build_opener(_NoRedirect)
LOCAL_OPENER = urllib.request.build_opener(_NoRedirect, urllib.request.ProxyHandler({}))


def opener_for(url: str) -> urllib.request.OpenerDirector:
    return LOCAL_OPENER if _is_loopback(urllib.parse.urlsplit(url).hostname or "") else OPENER


def _is_loopback(host: str) -> bool:
    if host in LOCAL_HOSTS:
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float, cancellation: Cancellation) -> dict[str, Any]:
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **headers}, method="POST")

    opener = opener_for(url)

    def send() -> bytes:
        with opener.open(request, timeout=timeout + SOCKET_GRACE_SECONDS) as response:
            return response.read(MAX_RESPONSE_BYTES + 1)

    try:
        body = run_cancellable(send, cancellation, timeout)
    except urllib.error.HTTPError as error:
        raise AiProviderError(f"{url} answered HTTP {error.code}: {_error_detail(error)}") from error
    except urllib.error.URLError as error:
        raise AiProviderError(f"Cannot reach {url}: {error.reason}") from error
    except (http.client.HTTPException, OSError) as error:
        raise AiProviderError(f"The connection to {url} failed: {error or type(error).__name__}") from error
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
