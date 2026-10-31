import time
from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from bussola.ai.base import AiError, AiProvider, Cancellation
from bussola.ai.runner import AiRunner, AiTask

MILLISECONDS = 1000
CONNECTION_TIMEOUT_SECONDS = 120.0
CONNECTION_MAX_TOKENS = 4096


class ConnectionCheck(BaseModel):
    ok: bool


CONNECTION_CHECK = AiTask(
    name="connection_check",
    version=1,
    system="You check that bussola can reach a language model. Answer only with JSON that matches the given schema.",
    output=ConnectionCheck,
    max_tokens=CONNECTION_MAX_TOKENS,
)
CONNECTION_PROMPT = 'Answer with {"ok": true}.'


@dataclass(frozen=True)
class ConnectionResult:
    ok: bool
    message: str
    elapsed_ms: int


def check_connection(connect: Callable[[], AiProvider], cancellation: Cancellation) -> ConnectionResult:
    started = time.monotonic()
    try:
        provider = connect()
        check = AiRunner(provider).run(CONNECTION_CHECK, CONNECTION_PROMPT, cancellation)
    except AiError as error:
        return ConnectionResult(False, str(error), _elapsed(started))
    if not check.ok:
        return ConnectionResult(False, f"{provider.label} answered, but not with the expected result", _elapsed(started))
    model = f" ({provider.model})" if provider.model else ""
    return ConnectionResult(True, f"{provider.label}{model} answered", _elapsed(started))


def _elapsed(started: float) -> int:
    return round((time.monotonic() - started) * MILLISECONDS)
