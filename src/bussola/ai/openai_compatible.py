import json
from typing import Any, cast

from bussola.ai.base import MAX_ERROR_LENGTH, MAX_TOOL_ROUNDS, AiOutputError, AiRequest, Cancellation, ToolOutcome, ToolRunner, json_object
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
        self.max_tokens = max_tokens

    def complete(self, request: AiRequest, cancellation: Cancellation) -> str:
        messages: list[dict[str, Any]] = [{"role": "system", "content": request.system}, {"role": "user", "content": request.prompt}]
        for _ in range(MAX_TOOL_ROUNDS):
            message = self._send(request, messages, cancellation)
            calls = [call for item in cast(list[Any], message.get("tool_calls") or []) if (call := json_object(item)) is not None]
            if not calls or request.tools is None:
                content = message.get("content")
                if not isinstance(content, str):
                    raise AiOutputError("The endpoint answered without any content")
                return content
            messages.append({"role": "assistant", "content": message.get("content"), "tool_calls": calls})
            messages += [{"role": "tool", "tool_call_id": call.get("id"), "content": _run(request.tools, call).text} for call in calls]
        raise AiOutputError(f"The model was still asking for tools after {MAX_TOOL_ROUNDS} rounds")

    def _send(self, request: AiRequest, messages: list[dict[str, Any]], cancellation: Cancellation) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "max_completion_tokens": request.max_tokens,
            "messages": messages,
            "response_format": {"type": "json_schema", "json_schema": {"name": request.name, "schema": request.schema, "strict": True}},
        }
        if request.tools is not None:
            payload["tools"] = [
                {"type": "function", "function": {"name": tool.name, "description": tool.description, "parameters": tool.schema, "strict": True}}
                for tool in request.tools.definitions
            ]
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        response = post_json(f"{self.endpoint}{COMPLETIONS_PATH}", headers, payload, self._timeout, cancellation)
        choice = _first_choice(response)
        if choice.get("finish_reason") == "length":
            raise AiOutputError("The answer was cut off before it was complete")
        message = json_object(choice.get("message")) or {}
        if message.get("refusal"):
            raise AiOutputError(f"The model declined to answer: {str(message['refusal'])[:MAX_ERROR_LENGTH]}")
        return message


def _run(tools: ToolRunner, call: dict[str, Any]) -> ToolOutcome:
    function = json_object(call.get("function")) or {}
    try:
        arguments = json_object(json.loads(str(function.get("arguments") or "{}")))
    except json.JSONDecodeError:
        arguments = None
    outcome = ToolOutcome("The arguments are not a JSON object", error=True) if arguments is None else tools.call(str(function.get("name")), arguments)
    return ToolOutcome(f"Error: {outcome.text}", error=True) if outcome.error else outcome


def _first_choice(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    first = json_object(cast(list[Any], choices)[0]) if isinstance(choices, list) and choices else None
    if first is None:
        raise AiOutputError("The endpoint answered without any choices")
    return first
