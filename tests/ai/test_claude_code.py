import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from bussola.ai.base import AiCancelledError, AiNotConfiguredError, AiProviderError, AiRequest, AiTimeoutError, Cancellation
from bussola.ai.claude_code import ClaudeCodeProvider, find_claude
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


def test_without_a_model_the_cli_default_is_used_and_the_text_result_is_read(fake_claude: FakeClaude) -> None:
    fake_claude.answer({"type": "result", "is_error": False, "result": '{"impact": "high"}'})

    answer = provider().complete(REQUEST, Cancellation())

    assert answer == '{"impact": "high"}'
    assert "--model" not in fake_claude.call()["args"]


def test_an_error_reported_by_the_cli_is_raised(fake_claude: FakeClaude) -> None:
    fake_claude.answer({"type": "result", "is_error": True, "result": "Not logged in. Run /login"}, exit_code=1)

    with pytest.raises(AiProviderError, match="Claude Code: Not logged in"):
        provider().complete(REQUEST, Cancellation())


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
    threading.Timer(0.5, cancellation.cancel).start()

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


def test_a_claude_command_that_cannot_run_is_reported(tmp_path: Path) -> None:
    broken = tmp_path / "claude"
    broken.write_text("not a program")

    with pytest.raises(AiProviderError, match="Cannot run claude"):
        ClaudeCodeProvider(str(broken), None, 5.0).complete(REQUEST, Cancellation())


def test_the_provider_needs_the_claude_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))

    with pytest.raises(AiNotConfiguredError, match="The claude command is not on PATH"):
        build_provider(AiSettings(ProviderName.CLAUDE_CODE))
