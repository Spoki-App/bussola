import json
import os
import shutil
import subprocess
import tempfile
from typing import Any

from bussola.ai.base import MAX_ERROR_LENGTH, AiNotConfiguredError, AiOutputError, AiProviderError, AiRequest, Cancellation, json_object, run_cancellable
from bussola.ai.config import PROVIDER_LABELS, ProviderName

CLAUDE = "claude"
CLAUDE_ENV = {"NO_COLOR": "1"}


def find_claude() -> str:
    executable = shutil.which(CLAUDE)
    if executable is None:
        raise AiNotConfiguredError("The claude command is not on PATH. Install Claude Code and run claude once to sign in.")
    return executable


class ClaudeCodeProvider:
    name: str = ProviderName.CLAUDE_CODE
    label = PROVIDER_LABELS[ProviderName.CLAUDE_CODE]

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
        arguments = ["-p", "--output-format", "json", "--no-session-persistence", "--tools", "", "--system-prompt", request.system]
        arguments += ["--json-schema", json.dumps(request.schema)]
        return [*arguments, "--model", self.model] if self.model else arguments

    def _run(self, command: list[str], prompt: str, cancellation: Cancellation) -> tuple[int, str, str]:
        with tempfile.TemporaryDirectory(prefix="bussola-ai-") as workdir:
            process = subprocess.Popen(
                command,
                cwd=workdir,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                env={**os.environ, **CLAUDE_ENV},
            )
            try:
                stdout, stderr = run_cancellable(lambda: process.communicate(prompt), cancellation, self._timeout)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
        return process.returncode, stdout, stderr


def _envelope(stdout: str) -> dict[str, Any] | None:
    try:
        return json_object(json.loads(stdout))
    except json.JSONDecodeError:
        return None
