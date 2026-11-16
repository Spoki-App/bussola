from typing import Any, cast

from bussola.ai.base import DEFAULT_TUNING, MAX_TOOL_ROUNDS, AiOutputError, AiRequest, Cancellation, ModelInfo, ToolRunner, Tuning, json_object
from bussola.ai.config import PROVIDER_LABELS, ProviderName
from bussola.ai.http import get_json, post_json

API_VERSION = "2026-10-21"
MESSAGES_PATH = "/v1/messages"
MODELS_PATH = "/v1/models?limit=1000"
STOP_MESSAGES = {
    "max_tokens": "The answer was cut off before it was complete",
    "model_context_window_exceeded": "The answer was cut off because the context window is full",
    "refusal": "The model declined to answer",
}
TOOL_USE = "tool_use"


class AnthropicProvider:
    name: str = ProviderName.ANTHROPIC
    label = PROVIDER_LABELS[ProviderName.ANTHROPIC]

    def __init__(self, model: str, endpoint: str, api_key: str, timeout: float, tuning: Tuning = DEFAULT_TUNING) -> None:
        self.model: str | None = model
        self.endpoint: str | None = endpoint
        self._api_key = api_key
        self._timeout = timeout
        self.max_tokens = tuning.max_tokens
        self.effort = tuning.effort

    def models(self, cancellation: Cancellation) -> list[ModelInfo]:
        response = get_json(f"{self.endpoint}{MODELS_PATH}", self._headers(), self._timeout, cancellation)
        return [_model_info(fields) for item in cast(list[Any], response.get("data") or []) if (fields := json_object(item)) and fields.get("id")]

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": self._api_key, "anthropic-version": API_VERSION}

    def complete(self, request: AiRequest, cancellation: Cancellation) -> str:
        messages: list[dict[str, Any]] = [{"role": "user", "content": request.prompt}]
        for _ in range(MAX_TOOL_ROUNDS):
            response = self._send(request, messages, cancellation)
            content = cast(list[Any], response.get("content")) if isinstance(response.get("content"), list) else []
            if response.get("stop_reason") != TOOL_USE or request.tools is None:
                return "".join(_text(block) for block in content)
            messages += [{"role": "assistant", "content": content}, {"role": "user", "content": _tool_results(request.tools, content)}]
        raise AiOutputError(f"The model was still asking for tools after {MAX_TOOL_ROUNDS} rounds")

    def _send(self, request: AiRequest, messages: list[dict[str, Any]], cancellation: Cancellation) -> dict[str, Any]:
        output_config: dict[str, Any] = {"format": {"type": "json_schema", "schema": request.schema}}
        if self.effort is not None:
            output_config["effort"] = self.effort
        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "system": request.system,
            "messages": messages,
            "output_config": output_config,
        }
        if request.tools is not None:
            payload["tools"] = [
                {"name": tool.name, "description": tool.description, "input_schema": tool.schema, "strict": True} for tool in request.tools.definitions
            ]
            payload["cache_control"] = {"type": "ephemeral"}
        response = post_json(f"{self.endpoint}{MESSAGES_PATH}", self._headers(), payload, self._timeout, cancellation)
        stop_message = STOP_MESSAGES.get(str(response.get("stop_reason")))
        if stop_message:
            raise AiOutputError(stop_message)
        return response


def _tool_results(tools: ToolRunner, content: list[Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for block in content:
        fields = json_object(block) or {}
        if fields.get("type") != TOOL_USE:
            continue
        outcome = tools.call(str(fields.get("name")), json_object(fields.get("input")) or {})
        result: dict[str, Any] = {"type": "tool_result", "tool_use_id": fields.get("id"), "content": outcome.text}
        if outcome.error:
            result["is_error"] = True
        results.append(result)
    return results


def _text(block: Any) -> str:
    fields = json_object(block) or {}
    return str(fields.get("text", "")) if fields.get("type") == "text" else ""


def _model_info(fields: dict[str, Any]) -> ModelInfo:
    effort = json_object((json_object(fields.get("capabilities")) or {}).get("effort"))
    supported = effort.get("supported") if effort is not None else None
    return ModelInfo(str(fields["id"]), supported if isinstance(supported, bool) else None)
