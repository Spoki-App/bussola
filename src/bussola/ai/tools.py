import json
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from bussola.ai.base import AiCancelledError, ToolDefinition, ToolOutcome, describe_validation_error
from bussola.ai.runner import output_schema

MAX_TOOL_OUTPUT_CHARACTERS = 20_000
REPORTED_ERRORS = 3
logger = logging.getLogger(__name__)


class ToolError(Exception):
    pass


@dataclass(frozen=True)
class AiTool[T: BaseModel]:
    name: str
    description: str
    input: type[T]
    run: Callable[[T], str]

    def definition(self) -> ToolDefinition:
        return ToolDefinition(self.name, self.description, output_schema(self.input))


class Toolbox:
    def __init__(self, tools: list[AiTool[Any]], max_calls: int) -> None:
        self._tools = {tool.name: tool for tool in tools}
        self._max_calls = max_calls
        self._lock = threading.Lock()
        self.calls = 0

    @property
    def definitions(self) -> tuple[ToolDefinition, ...]:
        return tuple(tool.definition() for tool in self._tools.values())

    def fingerprint(self) -> str:
        return json.dumps([[item.name, item.description, item.schema] for item in self.definitions], sort_keys=True)

    def call(self, name: str, arguments: dict[str, Any]) -> ToolOutcome:
        with self._lock:
            self.calls += 1
            spent = self.calls > self._max_calls
        if spent:
            return ToolOutcome(f"No tool calls are left ({self._max_calls} were used). Answer now with what you found.", error=True)
        tool = self._tools.get(name)
        if tool is None:
            return ToolOutcome(f"There is no tool named {name}. The tools are {', '.join(self._tools)}.", error=True)
        try:
            parsed = tool.input.model_validate(arguments)
        except ValidationError as error:
            return ToolOutcome(f"Invalid arguments: {describe_validation_error(error, REPORTED_ERRORS)}", error=True)
        try:
            return ToolOutcome(_clipped(tool.run(parsed)))
        except AiCancelledError:
            raise
        except ToolError as error:
            return ToolOutcome(str(error), error=True)
        except Exception as error:
            logger.exception("AI tool %s failed", name)
            return ToolOutcome(f"The tool failed: {error}", error=True)


def _clipped(text: str) -> str:
    if len(text) <= MAX_TOOL_OUTPUT_CHARACTERS:
        return text
    return f"{text[:MAX_TOOL_OUTPUT_CHARACTERS]}\n[... {len(text) - MAX_TOOL_OUTPUT_CHARACTERS} more characters not shown; ask for less]"
