import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from bussola.ai.base import AiCancelledError, AiNotConfiguredError, AiProviderError, AiRequest, AiTimeoutError, Cancellation, ToolDefinition, ToolOutcome
from bussola.ai.claude_code import READER_NAME, ClaudeCodeProvider, find_claude
from bussola.ai.config import AiSettings, ProviderName
from bussola.ai.providers import build_provider

FAKE_CLAUDE_DIR = Path(__file__).parent.parent / "fakeclaude"
REQUEST = AiRequest(name="rate", system="Rate the change.", prompt="def pay(): ...", schema={"type": "object"}, max_tokens=512)


class FakeClaude:
    def __init__(self, log: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.log = log
        self._monkeypatch = monkeypatch

    def answer(self, envelope: dict[str, Any] | str, exit_code: int = 0, stderr: str = "", sleep: float = 0) -> None:
        self._monkeypatch.setenv("FAKE_CLAUDE_STDOUT", envelope if isinstance(envelope, str) else json.dumps(envelope))
        self._monkeypatch.setenv("FAKE_CLAUDE_EXIT", str(exit_code))
        self._monkeypatch.setenv("FAKE_CLAUDE_STDERR", stderr)
        self._monkeypatch.setenv("FAKE_CLAUDE_SLEEP", str(sleep))

    def call(self) -> dict[str, Any]:
        return json.loads(self.log.read_text())


@pytest.fixture
def fake_claude(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeClaude:
    monkeypatch.setenv("FAKE_CLAUDE_LOG", str(tmp_path / "claude-call.json"))
    monkeypatch.setenv("PATH", f"{FAKE_CLAUDE_DIR}{os.pathsep}{os.environ['PATH']}")
    return FakeClaude(tmp_path / "claude-call.json", monkeypatch)


def provider(model: str | None = None, timeout: float = 10.0) -> ClaudeCodeProvider:
    return ClaudeCodeProvider(find_claude(), model, timeout)


def test_the_cli_runs_without_tools_with_the_schema_and_the_prompt_on_stdin(fake_claude: FakeClaude, tmp_path: Path) -> None:
    fake_claude.answer({"type": "result", "is_error": False, "result": "", "structured_output": {"impact": "low"}})

    answer = provider("claude-opus-5-5").complete(REQUEST, Cancellation())

    assert json.loads(answer) == {"impact": "low"}
    call = fake_claude.call()
    assert call["prompt"] == "def pay(): ..."
    assert call["args"] == [
        "-p",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--safe-mode",
        "--strict-mcp-config",
        "--tools",
        "",
        "--system-prompt",
        "Rate the change.",
        "--json-schema",
        '{"type": "object"}',
        "--model",
        "claude-opus-5-5",
    ]
    assert not Path(call["cwd"]).is_relative_to(tmp_path)
    assert Path(call["cwd"]).name.startswith("bussola-ai-")


def test_bussola_settings_such_as_the_session_token_are_not_passed_to_the_cli(fake_claude: FakeClaude, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUSSOLA_TOKEN", "session-secret")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SSE_PORT", "4242")
    monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
    monkeypatch.setenv("HOME_TOOL_SETTING", "kept")
    fake_claude.answer({"type": "result", "is_error": False, "result": "{}"})

    provider().complete(REQUEST, Cancellation())

    environment = fake_claude.call()["env"]
    assert "BUSSOLA_TOKEN" not in environment
    assert "CLAUDECODE" not in environment
    assert "CLAUDE_CODE_SSE_PORT" not in environment
    assert environment["CLAUDE_CODE_USE_BEDROCK"] == "1"
    assert environment["HOME_TOOL_SETTING"] == "kept"
    assert environment["NO_COLOR"] == "1"


def test_without_a_model_the_cli_default_is_used_and_the_text_result_is_read(fake_claude: FakeClaude) -> None:
    fake_claude.answer({"type": "result", "is_error": False, "result": '{"impact": "high"}'})

    answer = provider().complete(REQUEST, Cancellation())

    assert answer == '{"impact": "high"}'
    assert "--model" not in fake_claude.call()["args"]


def test_an_error_reported_by_the_cli_is_raised(fake_claude: FakeClaude) -> None:
    fake_claude.answer({"type": "result", "is_error": True, "result": "Not logged in. Run /login"}, exit_code=1)

    with pytest.raises(AiProviderError, match="Claude Code: Not logged in"):
        provider().complete(REQUEST, Cancellation())


def test_an_expired_sign_in_says_how_to_sign_in_again(fake_claude: FakeClaude) -> None:
    expired = "Failed to authenticate: OAuth session expired and could not be refreshed"
    fake_claude.answer({"type": "result", "is_error": True, "result": expired}, exit_code=1)

    with pytest.raises(AiProviderError) as raised:
        provider().complete(REQUEST, Cancellation())

    assert str(raised.value) == f"Claude Code: {expired}. Run claude in a terminal and sign in again with /login."


def test_a_cli_error_unrelated_to_sign_in_gets_no_sign_in_hint(fake_claude: FakeClaude) -> None:
    fake_claude.answer({"type": "result", "is_error": True, "result": "Prompt is too long"}, exit_code=1)

    with pytest.raises(AiProviderError) as raised:
        provider().complete(REQUEST, Cancellation())

    assert str(raised.value) == "Claude Code: Prompt is too long"


def test_a_crash_of_the_cli_reports_its_output(fake_claude: FakeClaude) -> None:
    fake_claude.answer("", exit_code=2, stderr="unknown option --json-schema")

    with pytest.raises(AiProviderError, match="claude exited with code 2: unknown option --json-schema"):
        provider().complete(REQUEST, Cancellation())


def test_a_slow_cli_is_stopped_at_the_timeout(fake_claude: FakeClaude) -> None:
    fake_claude.answer({"result": "{}"}, sleep=30)

    with pytest.raises(AiTimeoutError):
        provider(timeout=0.5).complete(REQUEST, Cancellation())


def test_a_running_cli_can_be_cancelled(fake_claude: FakeClaude) -> None:
    fake_claude.answer({"result": "{}"}, sleep=30)
    cancellation = Cancellation()
    threading.Timer(0.3, cancellation.cancel).start()

    with pytest.raises(AiCancelledError):
        provider().complete(REQUEST, cancellation)


def test_cancelling_also_stops_the_processes_the_cli_started(fake_claude: FakeClaude, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    child_pid_file = tmp_path / "child.pid"
    monkeypatch.setenv("FAKE_CLAUDE_CHILD_PID", str(child_pid_file))
    fake_claude.answer({"result": "{}"}, sleep=30)
    cancellation = Cancellation()

    def cancel_once_the_child_runs() -> None:
        deadline = time.monotonic() + 10
        while not child_pid_file.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        cancellation.cancel()

    threading.Thread(target=cancel_once_the_child_runs, daemon=True).start()

    with pytest.raises(AiCancelledError):
        provider().complete(REQUEST, cancellation)

    child_pid = child_pid_file.read_text()
    assert subprocess.run(["ps", "-o", "stat=", "-p", child_pid], capture_output=True, text=True, check=False).stdout.strip() in {"", "Z"}


def test_processes_left_behind_by_the_cli_do_not_hold_up_its_answer(fake_claude: FakeClaude, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    child_pid_file = tmp_path / "child.pid"
    monkeypatch.setenv("FAKE_CLAUDE_CHILD_PID", str(child_pid_file))
    fake_claude.answer({"type": "result", "is_error": False, "result": '{"impact": "low"}'})
    started = time.monotonic()

    answer = provider(timeout=20).complete(REQUEST, Cancellation())

    assert answer == '{"impact": "low"}'
    assert time.monotonic() - started < 5
    child_pid = child_pid_file.read_text()
    assert subprocess.run(["ps", "-o", "stat=", "-p", child_pid], capture_output=True, text=True, check=False).stdout.strip() in {"", "Z"}


def test_a_detached_process_left_by_the_cli_is_stopped(fake_claude: FakeClaude, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    child_pid_file = tmp_path / "detached.pid"
    monkeypatch.setenv("FAKE_CLAUDE_DETACHED_CHILD_PID", str(child_pid_file))
    fake_claude.answer({"type": "result", "is_error": False, "result": "{}"})

    provider().complete(REQUEST, Cancellation())

    child_pid = child_pid_file.read_text()
    assert subprocess.run(["ps", "-o", "stat=", "-p", child_pid], capture_output=True, text=True, check=False).stdout.strip() in {"", "Z"}


def test_a_process_in_another_session_holding_the_output_does_not_hold_up_the_answer(
    fake_claude: FakeClaude, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    child_pid_file = tmp_path / "escaped.pid"
    monkeypatch.setenv("FAKE_CLAUDE_ESCAPED_CHILD_PID", str(child_pid_file))
    fake_claude.answer({"type": "result", "is_error": False, "result": '{"impact": "high"}'})
    started = time.monotonic()

    try:
        answer = provider(timeout=20).complete(REQUEST, Cancellation())
    finally:
        os.kill(int(child_pid_file.read_text()), signal.SIGKILL)

    assert answer == '{"impact": "high"}'
    assert time.monotonic() - started < 5
    deadline = time.monotonic() + 2
    while any(thread.name == READER_NAME for thread in threading.enumerate()) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not any(thread.name == READER_NAME for thread in threading.enumerate())


def test_a_claude_command_that_cannot_run_is_reported(tmp_path: Path) -> None:
    broken = tmp_path / "claude"
    broken.write_text("not a program")

    with pytest.raises(AiProviderError, match="Cannot run claude"):
        ClaudeCodeProvider(str(broken), None, 5.0).complete(REQUEST, Cancellation())


def test_a_claude_without_safe_mode_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    old = tmp_path / "claude"
    old.write_text("#!/bin/sh\necho 'Usage: claude [options]'\n")
    old.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))

    with pytest.raises(AiNotConfiguredError, match="has no --safe-mode"):
        find_claude()


def test_the_version_check_runs_like_the_real_call_and_is_asked_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = tmp_path / "calls.log"
    checker = tmp_path / "claude"
    checker.write_text(f'#!/bin/sh\necho "$BUSSOLA_TOKEN|$(pwd)" >> {log}\nexit 3\n')
    checker.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("BUSSOLA_TOKEN", "session-secret")
    monkeypatch.chdir(tmp_path)

    for _ in range(3):
        with pytest.raises(AiNotConfiguredError, match="has no --safe-mode"):
            find_claude()

    calls = log.read_text().splitlines()
    assert len(calls) == 1
    token, cwd = calls[0].split("|")
    assert token == ""
    assert Path(cwd).resolve() != tmp_path.resolve()


def test_a_version_check_that_failed_is_tried_again_later(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = tmp_path / "calls.log"
    slow = tmp_path / "claude"
    slow.write_text(f"#!/bin/sh\necho run >> {log}\n{shutil.which('sleep')} 5\n")
    slow.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr("bussola.ai.claude_code.HELP_TIMEOUT_SECONDS", 0.2)
    monkeypatch.setattr("bussola.ai.claude_code.FAILED_CHECK_SECONDS", 0.0)

    for _ in range(2):
        with pytest.raises(AiNotConfiguredError, match="did not answer"):
            find_claude()

    assert log.read_text().splitlines() == ["run", "run"]


def test_a_claude_that_disappears_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    link = tmp_path / "claude"
    link.symlink_to(tmp_path / "gone")
    monkeypatch.setenv("PATH", str(tmp_path))

    def which(_name: str) -> str:
        return str(link)

    monkeypatch.setattr("shutil.which", which)

    with pytest.raises(AiNotConfiguredError, match="Cannot read"):
        find_claude()


def test_a_version_check_is_not_held_up_by_a_child_keeping_the_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    helper = tmp_path / "claude"
    helper.write_text(f"#!/bin/sh\necho '--safe-mode'\n{shutil.which('sleep')} 30 &\n")
    helper.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    started = time.monotonic()

    assert find_claude() == str(helper)
    assert time.monotonic() - started < 5


def test_a_cancelled_call_does_not_start_claude(fake_claude: FakeClaude) -> None:
    cancellation = Cancellation()
    cancellation.cancel()

    with pytest.raises(AiCancelledError):
        provider().complete(REQUEST, cancellation)

    assert not fake_claude.log.exists()


def test_claude_code_is_reported_as_unsupported_on_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")

    with pytest.raises(AiNotConfiguredError, match="not supported on Windows"):
        find_claude()


def test_the_provider_needs_the_claude_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))

    with pytest.raises(AiNotConfiguredError, match="The claude command is not on PATH"):
        build_provider(AiSettings(ProviderName.CLAUDE_CODE))


class EchoTools:
    definitions = (ToolDefinition("read_file", "Lines of a file.", {"type": "object", "properties": {"path": {"type": "string"}}}),)

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, name: str, arguments: dict[str, Any]) -> ToolOutcome:
        self.calls.append((name, arguments))
        return ToolOutcome(f"1: contents of {arguments['path']}")


def test_tools_reach_the_cli_as_its_only_mcp_server_without_user_settings(fake_claude: FakeClaude, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_claude.answer({"type": "result", "is_error": False, "result": "", "structured_output": {"findings": []}})
    monkeypatch.setenv("FAKE_CLAUDE_MCP_CALL", json.dumps({"name": "read_file", "arguments": {"path": "app.py"}}))
    monkeypatch.setenv("FAKE_CLAUDE_MCP_LOG", str(tmp_path / "mcp.json"))
    tools = EchoTools()

    answer = provider("claude-opus-5-5").complete(replace(REQUEST, tools=tools), Cancellation())

    assert json.loads(answer) == {"findings": []}
    assert tools.calls == [("read_file", {"path": "app.py"})]
    initialized, listed, called = json.loads((tmp_path / "mcp.json").read_text())
    assert initialized["result"]["protocolVersion"] == "2025-06-18"
    assert listed["result"]["tools"] == [{"name": "read_file", "description": "Lines of a file.", "inputSchema": tools.definitions[0].schema}]
    assert called["result"] == {"content": [{"type": "text", "text": "1: contents of app.py"}], "isError": False}
    args = fake_claude.call()["args"]
    assert "--safe-mode" not in args
    assert args[args.index("--setting-sources") + 1] == ""
    assert args[args.index("--tools") + 1] == ""
    assert args[args.index("--allowedTools") + 1] == "mcp__bussola__read_file"
    assert {"--disable-slash-commands", "--strict-mcp-config"} <= set(args)
    server = json.loads(args[args.index("--mcp-config") + 1])["mcpServers"]["bussola"]
    assert server["type"] == "http"
    assert server["url"].startswith("http://127.0.0.1:")


def test_the_tool_server_stops_when_the_cli_is_done(fake_claude: FakeClaude) -> None:
    fake_claude.answer({"type": "result", "is_error": False, "result": "{}"})

    provider().complete(replace(REQUEST, tools=EchoTools()), Cancellation())

    args = fake_claude.call()["args"]
    url: str = json.loads(args[args.index("--mcp-config") + 1])["mcpServers"]["bussola"]["url"]
    port = urllib.parse.urlsplit(url).port
    assert port is not None
    with pytest.raises(ConnectionRefusedError):
        socket.create_connection(("127.0.0.1", port), timeout=2)
