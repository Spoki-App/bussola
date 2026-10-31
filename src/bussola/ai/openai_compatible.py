from typing import Any, cast

from bussola.ai.base import MAX_ERROR_LENGTH, AiOutputError, AiRequest, Cancellation, json_object
from bussola.ai.config import PROVIDER_LABELS, ProviderName
from bussola.ai.http import post_json

COMPLETIONS_PATH = "/chat/completions"


class OpenAiCompatibleProvider:
    name: str = ProviderName.OPENAI_COMPATIBLE
    label = PROVIDER_LABELS[ProviderName.OPENAI_COMPATIBLE]

    def __init__(self, model: str, endpoint: str, api_key: str | None, timeout: float, max_tokens: int | None = None) -> None:
        self.model: str | None = model
        self.endpoint: str | None = endpoint
        self._api_key = api_key
        self._timeout = timeout
        self._max_tokens = max_tokens

    def complete(self, request: AiRequest, cancellation: Cancellation) -> str:
        payload = {
            "model": self.model,
            "max_completion_tokens": min(request.max_tokens, self._max_tokens or request.max_tokens),
            "messages": [{"role": "system", "content": request.system}, {"role": "user", "content": request.prompt}],
            "response_format": {"type": "json_schema", "json_schema": {"name": request.name, "schema": request.schema, "strict": True}},
        }
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        response = post_json(f"{self.endpoint}{COMPLETIONS_PATH}", headers, payload, self._timeout, cancellation)
        choice = _first_choice(response)
        if choice.get("finish_reason") == "length":
            raise AiOutputError("The answer was cut off before it was complete")
        message = json_object(choice.get("message")) or {}
        if message.get("refusal"):
            raise AiOutputError(f"The model declined to answer: {str(message['refusal'])[:MAX_ERROR_LENGTH]}")
        content = message.get("content")
        if not isinstance(content, str):
            raise AiOutputError("The endpoint answered without any content")
        return content


def _first_choice(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    first = json_object(cast(list[Any], choices)[0]) if isinstance(choices, list) and choices else None
    if first is None:
        raise AiOutputError("The endpoint answered without any choices")
    return first
