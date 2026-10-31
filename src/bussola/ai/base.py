import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, wait
from dataclasses import dataclass
from typing import Any, Protocol, cast

POLL_SECONDS = 0.05
WORKER_NAME = "bussola-ai-call"
MAX_ERROR_LENGTH = 300


class AiError(Exception):
    pass


class AiNotConfiguredError(AiError):
    pass


class AiProviderError(AiError):
    pass


class AiUnreachableError(AiProviderError):
    pass


class AiRejectedError(AiProviderError):
    pass


class AiOutputError(AiError):
    pass


class AiTimeoutError(AiError):
    pass


class AiCancelledError(AiError):
    pass


class AiTargetChangedError(AiError):
    pass


@dataclass(frozen=True)
class AiRequest:
    name: str
    system: str
    prompt: str
    schema: dict[str, Any]
    max_tokens: int


class AiProvider(Protocol):
    name: str
    label: str
    model: str | None
    endpoint: str | None
    max_tokens: int | None

    def complete(self, request: AiRequest, cancellation: "Cancellation") -> str: ...


class Cancellation:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        if self.cancelled:
            raise AiCancelledError("Cancelled")


def run_cancellable[T](work: Callable[[], T], cancellation: Cancellation, timeout: float, abort: Callable[[], None] | None = None) -> T:
    cancellation.check()
    future: Future[T] = Future()

    def target() -> None:
        try:
            future.set_result(work())
        except BaseException as error:
            future.set_exception(error)

    threading.Thread(target=target, name=WORKER_NAME, daemon=True).start()
    deadline = time.monotonic() + timeout
    try:
        while not future.done():
            cancellation.check()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _timed_out(timeout)
            wait([future], timeout=min(POLL_SECONDS, remaining))
    except AiError:
        if abort is not None:
            abort()
        raise
    try:
        return future.result()
    except TimeoutError as error:
        raise _timed_out(timeout) from error


def _timed_out(timeout: float) -> AiTimeoutError:
    return AiTimeoutError(f"No answer within {timeout:g} seconds")


def json_object(value: Any) -> dict[str, Any] | None:
    return cast(dict[str, Any], value) if isinstance(value, dict) else None
