import threading
import time
from collections.abc import Callable
from concurrent.futures import Future, wait
from dataclasses import dataclass
from typing import Any, Protocol, cast

POLL_SECONDS = 0.05


class AiError(Exception):
    pass


class AiNotConfiguredError(AiError):
    pass


class AiProviderError(AiError):
    pass


class AiOutputError(AiError):
    pass


class AiTimeoutError(AiError):
    pass


class AiCancelledError(AiError):
    pass


@dataclass(frozen=True)
class AiRequest:
    name: str
    system: str
    prompt: str
    schema: dict[str, Any]
    max_tokens: int = 4096


class AiProvider(Protocol):
    name: str
    label: str
    model: str | None
    endpoint: str | None

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


def run_cancellable[T](work: Callable[[], T], cancellation: Cancellation, timeout: float) -> T:
    cancellation.check()
    future: Future[T] = Future()

    def target() -> None:
        try:
            future.set_result(work())
        except BaseException as error:
            future.set_exception(error)

    threading.Thread(target=target, daemon=True).start()
    deadline = time.monotonic() + timeout
    while not future.done():
        cancellation.check()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AiTimeoutError(f"No answer within {timeout:g} seconds")
        wait([future], timeout=min(POLL_SECONDS, remaining))
    return future.result()


def json_object(value: Any) -> dict[str, Any] | None:
    return cast(dict[str, Any], value) if isinstance(value, dict) else None
