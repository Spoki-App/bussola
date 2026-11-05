import http.client
import json
import urllib.parse
from typing import Any

from pydantic import BaseModel

from bussola.ai.base import ToolOutcome
from bussola.ai.mcp import serve_tools
from bussola.ai.tools import MAX_TOOL_OUTPUT_CHARACTERS, AiTool, Toolbox, ToolError


class Lines(BaseModel):
    path: str
    count: int


def read(lines: Lines) -> str:
    if lines.path == "missing.py":
        raise ToolError("missing.py does not exist")
    if lines.path == "broken.py":
        raise RuntimeError("disk on fire")
    return "x" * lines.count


def toolbox(max_calls: int = 5) -> Toolbox:
    return Toolbox([AiTool("read_file", "Lines of a file.", Lines, read)], max_calls)


def test_a_tool_gets_validated_arguments_and_publishes_a_strict_schema() -> None:
    tools = toolbox()

    assert tools.call("read_file", {"path": "app.py", "count": 3}) == ToolOutcome("xxx")
    [definition] = tools.definitions
    assert definition.schema["required"] == ["path", "count"]
    assert definition.schema["additionalProperties"] is False


def test_bad_calls_come_back_as_errors_the_model_can_read() -> None:
    tools = toolbox()

    assert tools.call("read_file", {"path": "app.py"}).text.startswith("Invalid arguments: count")
    assert tools.call("write_file", {}) == ToolOutcome("There is no tool named write_file. The tools are read_file.", error=True)
    assert tools.call("read_file", {"path": "missing.py", "count": 1}) == ToolOutcome("missing.py does not exist", error=True)
    assert tools.call("read_file", {"path": "broken.py", "count": 1}) == ToolOutcome("The tool failed: disk on fire", error=True)


def test_calls_past_the_budget_are_refused() -> None:
    tools = toolbox(max_calls=1)
    tools.call("read_file", {"path": "app.py", "count": 1})

    refused = tools.call("read_file", {"path": "app.py", "count": 1})

    assert refused.error
    assert "Answer now" in refused.text


def test_a_long_answer_is_clipped() -> None:
    text = toolbox().call("read_file", {"path": "app.py", "count": MAX_TOOL_OUTPUT_CHARACTERS + 10}).text

    assert text.endswith("[... 10 more characters not shown; ask for less]")


def post(url: str, message: Any) -> tuple[int, Any]:
    parts = urllib.parse.urlsplit(url)
    connection = http.client.HTTPConnection(parts.hostname or "", parts.port, timeout=5)
    try:
        connection.request("POST", parts.path, json.dumps(message), {"Content-Type": "application/json"})
        response = connection.getresponse()
        body = response.read()
    finally:
        connection.close()
    return response.status, json.loads(body) if body else None


def test_the_mcp_server_answers_requests_and_accepts_notifications() -> None:
    with serve_tools(toolbox()) as url:
        assert post(url, {"jsonrpc": "2.0", "method": "notifications/initialized"}) == (202, None)
        status, unknown = post(url, {"jsonrpc": "2.0", "id": 7, "method": "resources/list"})
        assert (status, unknown["error"]["code"]) == (200, -32601)
        assert post(url, {"jsonrpc": "2.0", "id": 8, "method": "ping"}) == (200, {"jsonrpc": "2.0", "id": 8, "result": {}})


def test_the_mcp_server_answers_only_on_its_secret_path() -> None:
    with serve_tools(toolbox()) as url:
        other = url.rsplit("/", 1)[0] + "/guess"
        assert post(other, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}) == (404, None)
