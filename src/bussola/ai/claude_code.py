import contextlib
import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from typing import IO, Any

from bussola.ai.base import MAX_ERROR_LENGTH, AiNotConfiguredError, AiOutputError, AiProviderError, AiRequest, Cancellation, json_object, run_cancellable
from bussola.ai.config import PROVIDER_LABELS, ProviderName

CLAUDE = "claude"
CLAUDE_ENV = {"NO_COLOR": "1"}
PRIVATE_ENV_PREFIX = "BUSSOLA_"
PIPE_GRACE_SECONDS = 0.5
EXIT_POLL_SECONDS = 0.05


def find_claude() -> str:
    executable = shutil.which(CLAUDE)
    if executable is None:
        raise AiNotConfiguredError("The claude command is not on PATH. Install Claude Code and run claude once to sign in.")
    return executable


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
            "--safe-mode",
            "--strict-mcp-config",
            "--tools",
            "",
            "--system-prompt",
            request.system,
        ]
        arguments += ["--json-schema", json.dumps(request.schema)]
        return [*arguments, "--model", self.model] if self.model else arguments

    def _run(self, command: list[str], prompt: str, cancellation: Cancellation) -> tuple[int, str, str]:
        with tempfile.TemporaryDirectory(prefix="bussola-ai-") as workdir:
            try:
                process = subprocess.Popen(
                    command,
                    cwd=workdir,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
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
    inherited = {name: value for name, value in os.environ.items() if not name.startswith(PRIVATE_ENV_PREFIX)}
    return {**inherited, **CLAUDE_ENV}


class _ClaudeSession:
    def __init__(self, process: subprocess.Popen[str]) -> None:
        self._process = process
        self._lock = threading.Lock()

    def exchange(self, prompt: str) -> tuple[int, str, str]:
        output: dict[str, str] = {}
        readers = [
            threading.Thread(target=_read_into, args=(stream, output, name), daemon=True)
            for name, stream in (("stdout", self._process.stdout), ("stderr", self._process.stderr))
        ]
        for reader in readers:
            reader.start()
        self._send(prompt)
        self._wait_for_exit()
        self._stop_group()
        returncode = self._reap()
        for reader in readers:
            reader.join(PIPE_GRACE_SECONDS)
        if any(reader.is_alive() for reader in readers):
            _kill_group(self._process)
            for reader in readers:
                reader.join()
        return returncode, output.get("stdout", ""), output.get("stderr", "")

    def finish(self) -> None:
        self._stop_group()
        self._reap()

    def _send(self, prompt: str) -> None:
        stdin = self._process.stdin
        if stdin is not None:
            with contextlib.suppress(BrokenPipeError, ValueError):
                stdin.write(prompt)
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


def _read_into(stream: IO[str] | None, output: dict[str, str], name: str) -> None:
    if stream is not None:
        output[name] = stream.read()


def _kill_group(process: subprocess.Popen[str]) -> None:
    with contextlib.suppress(OSError):
        os.killpg(process.pid, signal.SIGKILL)


def _envelope(stdout: str) -> dict[str, Any] | None:
    try:
        return json_object(json.loads(stdout))
    except json.JSONDecodeError:
        return None
