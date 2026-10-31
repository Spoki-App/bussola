import http.client
import json
import urllib.error
import urllib.request
from typing import Any

from bussola.ai.base import MAX_ERROR_LENGTH, AiProviderError, Cancellation, json_object, run_cancellable

SOCKET_GRACE_SECONDS = 5.0


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


OPENER = urllib.request.build_opener(_NoRedirect)


def post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float, cancellation: Cancellation) -> dict[str, Any]:
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **headers}, method="POST")

    def send() -> bytes:
        with OPENER.open(request, timeout=timeout + SOCKET_GRACE_SECONDS) as response:
            return response.read()

    try:
        body = run_cancellable(send, cancellation, timeout)
    except urllib.error.HTTPError as error:
        raise AiProviderError(f"{url} answered HTTP {error.code}: {_error_detail(error)}") from error
    except urllib.error.URLError as error:
        raise AiProviderError(f"Cannot reach {url}: {error.reason}") from error
    except (http.client.HTTPException, OSError) as error:
        raise AiProviderError(f"The connection to {url} failed: {error or type(error).__name__}") from error
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
