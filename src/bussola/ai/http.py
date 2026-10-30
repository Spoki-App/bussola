import json
import urllib.error
import urllib.request
from typing import Any

from bussola.ai.base import AiProviderError, Cancellation, json_object, run_cancellable

MAX_ERROR_LENGTH = 300
HTTP_SCHEMES = ("http://", "https://")


def post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float, cancellation: Cancellation) -> dict[str, Any]:
    if not url.startswith(HTTP_SCHEMES):
        raise AiProviderError(f"{url} is not an http or https address")
    request = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json", **headers}, method="POST")

    def send() -> bytes:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()

    try:
        body = run_cancellable(send, cancellation, timeout)
    except urllib.error.HTTPError as error:
        raise AiProviderError(f"{url} answered HTTP {error.code}: {_error_detail(error)}") from error
    except urllib.error.URLError as error:
        raise AiProviderError(f"Cannot reach {url}: {error.reason}") from error
    except TimeoutError as error:
        raise AiProviderError(f"Cannot reach {url}: timed out") from error
    try:
        decoded = json_object(json.loads(body))
    except json.JSONDecodeError as error:
        raise AiProviderError(f"{url} did not answer with JSON") from error
    if decoded is None:
        raise AiProviderError(f"{url} answered with unexpected JSON")
    return decoded


def _error_detail(error: urllib.error.HTTPError) -> str:
    text = error.read().decode(errors="replace")
    try:
        payload = json_object(json.loads(text)) or {}
    except json.JSONDecodeError:
        payload = {}
    message = (json_object(payload.get("error")) or payload).get("message")
    return str(message or text or error.reason)[:MAX_ERROR_LENGTH]
