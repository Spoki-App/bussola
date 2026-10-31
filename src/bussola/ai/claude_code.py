import contextlib
import json
import os
import selectors
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Any

from bussola.ai.base import (
    MAX_ERROR_LENGTH,
    AiCancelledError,
    AiNotConfiguredError,
    AiOutputError,
    AiProviderError,
    AiRequest,
    Cancellation,
    json_object,
    run_cancellable,
)
from bussola.ai.config import PROVIDER_LABELS, ProviderName

CLAUDE = "claude"
CLAUDE_ENV = {"NO_COLOR": "1"}
PRIVATE_ENV_PREFIX = "BUSSOLA_"
PIPE_GRACE_SECONDS = 0.5
REQUIRED_FLAG = "--safe-mode"
READER_NAME = "bussola-claude-output"
HELP_TIMEOUT_SECONDS = 15.0
FAILED_CHECK_SECONDS = 60.0
FINISH_WAIT_SECONDS = 5.0
NESTED_SESSION_ENV = "CLAUDECODE"
READ_CHUNK_BYTES = 64 * 1024
EXIT_POLL_SECONDS = 0.05


def find_claude() -> str:
    executable = shutil.which(CLAUDE)
    if executable is None:
        raise AiNotConfiguredError("The claude command is not on PATH. Install Claude Code and run claude once to sign in.")
    try:
        modified = Path(executable).stat().st_mtime
    except OSError as error:
        raise AiNotConfiguredError(f"Cannot read {executable}: {error}") from error
    problem = _version_problem(executable, modified)
    if problem is not None:
        raise AiNotConfiguredError(problem)
    return executable


@dataclass(frozen=True)
class _VersionCheck:
    problem: str | None
    lasting: bool
    checked_at: float


_version_checks: dict[str, tuple[float, _VersionCheck]] = {}
_version_locks: dict[str, threading.Lock] = {}
_version_locks_guard = threading.Lock()


def _version_problem(executable: str, modified: float) -> str | None:
    with _version_locks_guard:
        lock = _version_locks.setdefault(executable, threading.Lock())
    with lock:
        cached_modified, cached = _version_checks.get(executable, (None, None))
        if cached is not None and cached_modified == modified and (cached.lasting or time.monotonic() - cached.checked_at < FAILED_CHECK_SECONDS):
            return cached.problem
        problem, lasting = _check_version(executable)
        _version_checks[executable] = (modified, _VersionCheck(problem, lasting, time.monotonic()))
        return problem


def _check_version(executable: str) -> tuple[str | None, bool]:
    with tempfile.TemporaryFile() as output:
        try:
            process = subprocess.Popen(
                [executable, "--help"],
                cwd=tempfile.gettempdir(),
                env=_claude_environment(),
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as error:
            return f"Cannot run claude --help: {error}", False
        try:
            process.wait(timeout=HELP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            _kill_group(process)
            process.wait()
            return f"claude --help did not answer within {HELP_TIMEOUT_SECONDS:g} seconds", False
        output.seek(0)
        help_text = output.read().decode(errors="replace")
    if REQUIRED_FLAG in help_text:
        return None, True
    return f"This version of Claude Code has no {REQUIRED_FLAG}. Update it with claude update.", True


class ClaudeCodeProvider:
    name: str = ProviderName.CLAUDE_CODE
    label = PROVIDER_LABELS[ProviderName.CLAUDE_CODE]
    endpoint: str | None = None
    max_tokens: int | None = None

    def __init__(self, executable: str, model: str | None, timeout: float) -> None:
        self.model = model
        self._executable = executable
        self._timeout = timeout

    def complete(self, request: AiRequest, cancellation: Cancellation) -> str:
        returncode, stdout, stderr = self._run([self._executable, *self._arguments(request)], request.prompt, cancellation)
        envelope = _envelope(stdout)
        if envelope is None:
            detail = (stderr or stdout).strip()[-MAX_ERROR_LENGTH:]
            raise AiProviderError(f"claude exited with code {returncode}: {detail}" if returncode else "claude did not answer with JSON")
        if envelope.get("is_error") or returncode:
            raise AiProviderError(f"Claude Code: {str(envelope.get('result') or 'request failed')[:MAX_ERROR_LENGTH]}")
        structured = envelope.get("structured_output")
        if structured is not None:
            return json.dumps(structured)
        result = envelope.get("result")
        if not isinstance(result, str):
            raise AiOutputError("Claude Code answered without a result")
        return result

    def _arguments(self, request: AiRequest) -> list[str]:
        arguments = [
            "-p",
            "--output-format",
            "json",
            "--no-session-persistence",
            REQUIRED_FLAG,
            "--strict-mcp-config",
            "--tools",
            "",
            "--system-prompt",
            request.system,
        ]
        arguments += ["--json-schema", json.dumps(request.schema)]
        return [*arguments, "--model", self.model] if self.model else arguments

    def _run(self, command: list[str], prompt: str, cancellation: Cancellation) -> tuple[int, str, str]:
        cancellation.check()
        with tempfile.TemporaryDirectory(prefix="bussola-ai-", ignore_cleanup_errors=True) as workdir:
            try:
                process = subprocess.Popen(
                    command,
                    cwd=workdir,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=_claude_environment(),
                    start_new_session=True,
                )
            except OSError as error:
                raise AiProviderError(f"Cannot run claude: {error}") from error
            session = _ClaudeSession(process)
            try:
                return run_cancellable(lambda: session.exchange(prompt), cancellation, self._timeout)
            finally:
                session.finish()


def _claude_environment() -> dict[str, str]:
    inherited = {name: value for name, value in os.environ.items() if not name.startswith(PRIVATE_ENV_PREFIX) and name != NESTED_SESSION_ENV}
    return {**inherited, **CLAUDE_ENV}


class _ClaudeSession:
    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self._process = process
        self._lock = threading.Lock()
        self._started = False
        self._abandoned = False
        self._exchanged = threading.Event()

    def exchange(self, prompt: str) -> tuple[int, str, str]:
        with self._lock:
            if self._abandoned:
                raise AiCancelledError("Cancelled")
            self._started = True
        try:
            return self._exchange(prompt)
        finally:
            self._exchanged.set()

    def _exchange(self, prompt: str) -> tuple[int, str, str]:
        stdout, stderr = _Collector(self._process.stdout), _Collector(self._process.stderr)
        self._send(prompt)
        self._wait_for_exit()
        self._stop_group()
        returncode = self._reap()
        return returncode, stdout.finish(PIPE_GRACE_SECONDS), stderr.finish(PIPE_GRACE_SECONDS)

    def finish(self) -> None:
        with self._lock:
            self._abandoned = True
            started = self._started
        self._stop_group()
        if started:
            self._exchanged.wait(FINISH_WAIT_SECONDS)
        self._reap()

    def _send(self, prompt: str) -> None:
        stdin = self._process.stdin
        if stdin is not None:
            with contextlib.suppress(BrokenPipeError, ValueError):
                stdin.write(prompt.encode())
            with contextlib.suppress(OSError):
                stdin.close()

    def _wait_for_exit(self) -> None:
        if hasattr(os, "waitid"):
            with contextlib.suppress(ChildProcessError):
                os.waitid(os.P_PID, self._process.pid, os.WEXITED | os.WNOWAIT)
            return
        while True:
            with self._lock:
                if self._process.poll() is not None:
                    return
            time.sleep(EXIT_POLL_SECONDS)

    def _stop_group(self) -> None:
        with self._lock:
            if self._process.returncode is None:
                _kill_group(self._process)

    def _reap(self) -> int:
        with self._lock:
            return self._process.wait()


class _Collector:
    def __init__(self, stream: IO[bytes] | None) -> None:
        self._chunks: list[bytes] = []
        self._lock = threading.Lock()
        self._done = threading.Event()
        self._stopped = threading.Event()
        if stream is None:
            self._done.set()
        else:
            threading.Thread(target=self._read, args=(stream,), name=READER_NAME, daemon=True).start()

    def finish(self, grace: float) -> str:
        if not self._done.wait(grace):
            self._stopped.set()
            self._done.wait(grace)
        with self._lock:
            return b"".join(self._chunks).decode(errors="replace")

    def _read(self, stream: IO[bytes]) -> None:
        with contextlib.suppress(OSError, ValueError), selectors.DefaultSelector() as selector:
            selector.register(stream, selectors.EVENT_READ)
            while not self._stopped.is_set():
                if not selector.select(timeout=EXIT_POLL_SECONDS):
                    continue
                chunk = os.read(stream.fileno(), READ_CHUNK_BYTES)
                if not chunk:
                    break
                with self._lock:
                    self._chunks.append(chunk)
        with contextlib.suppress(OSError):
            stream.close()
        self._done.set()


def _kill_group(process: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(OSError):
        os.killpg(process.pid, signal.SIGKILL)


def _envelope(stdout: str) -> dict[str, Any] | None:
    try:
        return json_object(json.loads(stdout))
    except json.JSONDecodeError:
        return None
