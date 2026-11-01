from typing import Any, cast

from bussola.ai.base import AiOutputError, AiRequest, Cancellation, json_object
from bussola.ai.config import PROVIDER_LABELS, ProviderName
from bussola.ai.http import post_json

API_VERSION = "2026-10-21"
MESSAGES_PATH = "/v1/messages"
STOP_MESSAGES = {
    "max_tokens": "The answer was cut off before it was complete",
    "model_context_window_exceeded": "The answer was cut off because the context window is full",
    "refusal": "The model declined to answer",
}


class AnthropicProvider:
    name: str = ProviderName.ANTHROPIC
    label = PROVIDER_LABELS[ProviderName.ANTHROPIC]

    def __init__(self, model: str, endpoint: str, api_key: str, timeout: float, max_tokens: int | None = None) -> None:
        self.model: str | None = model
        self.endpoint: str | None = endpoint
        self._api_key = api_key
        self._timeout = timeout
        self.max_tokens = max_tokens

    def complete(self, request: AiRequest, cancellation: Cancellation) -> str:
        payload = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "system": request.system,
            "messages": [{"role": "user", "content": request.prompt}],
            "output_config": {"format": {"type": "json_schema", "schema": request.schema}},
        }
        headers = {"x-api-key": self._api_key, "anthropic-version": API_VERSION}
        response = post_json(f"{self.endpoint}{MESSAGES_PATH}", headers, payload, self._timeout, cancellation)
        stop_message = STOP_MESSAGES.get(str(response.get("stop_reason")))
        if stop_message:
            raise AiOutputError(stop_message)
        content = response.get("content")
        return "".join(_text(block) for block in cast(list[Any], content)) if isinstance(content, list) else ""


def _text(block: Any) -> str:
    fields = json_object(block) or {}
    return str(fields.get("text", "")) if fields.get("type") == "text" else ""
