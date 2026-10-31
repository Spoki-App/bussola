import re
from dataclasses import dataclass
from typing import Any, Protocol, cast

from pydantic import BaseModel, ValidationError

from bussola.ai.base import AiOutputError, AiProvider, AiRequest, Cancellation

DEFAULT_MAX_TOKENS = 16000
NAME_MAPS = frozenset({"properties", "$defs"})
UNSUPPORTED_KEYWORDS = frozenset(
    {
        "default",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "maxItems",
        "maxLength",
        "maxProperties",
        "maximum",
        "minItems",
        "minLength",
        "minProperties",
        "minimum",
        "multipleOf",
        "uniqueItems",
    }
)
CODE_FENCE = re.compile(r"^```[\w-]*\s*(?P<body>.*?)\s*```$", re.DOTALL)
REPORTED_ERRORS = 3


@dataclass(frozen=True)
class AiTask[T: BaseModel]:
    name: str
    version: int
    system: str
    output: type[T]
    max_tokens: int = DEFAULT_MAX_TOKENS


@dataclass(frozen=True)
class AiCacheKey:
    task: str
    prompt_version: int
    provider: str
    model: str
    endpoint: str
    content_hash: str


class AiCache(Protocol):
    def get(self, key: AiCacheKey) -> dict[str, Any] | None: ...
    def put(self, key: AiCacheKey, result: dict[str, Any]) -> None: ...


class AiRunner:
    def __init__(self, provider: AiProvider, cache: AiCache | None = None) -> None:
        self.provider = provider
        self._cache = cache

    def run[T: BaseModel](self, task: AiTask[T], prompt: str, cancellation: Cancellation, content_hash: str | None = None) -> T:
        key = self._key(task, content_hash)
        cached = self._cached(task, key)
        if cached is not None:
            return cached
        request = AiRequest(task.name, task.system, prompt, output_schema(task.output), min(task.max_tokens, self.provider.max_tokens or task.max_tokens))
        result = parse_output(self.provider.complete(request, cancellation), task.output)
        if key is not None and self._cache is not None:
            self._cache.put(key, result.model_dump(mode="json"))
        return result

    def _key(self, task: AiTask[Any], content_hash: str | None) -> AiCacheKey | None:
        if content_hash is None or self._cache is None or self.provider.model is None:
            return None
        return AiCacheKey(task.name, task.version, self.provider.name, self.provider.model, self.provider.endpoint or "", content_hash)

    def _cached[T: BaseModel](self, task: AiTask[T], key: AiCacheKey | None) -> T | None:
        stored = self._cache.get(key) if key is not None and self._cache is not None else None
        if stored is None:
            return None
        try:
            return task.output.model_validate(stored)
        except ValidationError:
            return None


def output_schema(output: type[BaseModel]) -> dict[str, Any]:
    return _portable(output.model_json_schema())


def parse_output[T: BaseModel](text: str, output: type[T]) -> T:
    stripped = text.strip()
    fenced = CODE_FENCE.match(stripped)
    try:
        return output.model_validate_json(fenced.group("body") if fenced else stripped)
    except ValidationError as error:
        raise AiOutputError(f"The model's answer does not match the expected format: {_summary(error)}") from error


def _portable(schema: Any) -> Any:
    if isinstance(schema, list):
        return [_portable(item) for item in cast(list[Any], schema)]
    if not isinstance(schema, dict):
        return schema
    node: dict[str, Any] = {}
    for key, value in cast(dict[str, Any], schema).items():
        if key in NAME_MAPS:
            node[key] = {name: _portable(item) for name, item in cast(dict[str, Any], value).items()}
        elif key not in UNSUPPORTED_KEYWORDS:
            node[key] = _portable(value)
    if node.get("type") == "object" and "additionalProperties" not in node:
        node["additionalProperties"] = False
    if "properties" in node:
        node["required"] = list(node["properties"])
    return node


def _summary(error: ValidationError) -> str:
    problems = [f"{'.'.join(str(part) for part in item['loc']) or 'answer'}: {item['msg']}" for item in error.errors()[:REPORTED_ERRORS]]
    return "; ".join(problems)
