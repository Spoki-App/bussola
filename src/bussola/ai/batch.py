from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass, field

from bussola.ai.base import (
    AiCancelledError,
    AiError,
    AiNotConfiguredError,
    AiRejectedError,
    AiTargetChangedError,
    AiUnreachableError,
    Cancellation,
)

SAME_ERRORS_IN_A_ROW_TO_STOP = 2
STOPPING_ERRORS = (AiNotConfiguredError, AiTargetChangedError, AiUnreachableError, AiRejectedError)


@dataclass(frozen=True)
class BatchProgress:
    done: int
    failed: int
    total: int


@dataclass
class BatchResult[K: Hashable, T]:
    results: dict[K, T] = field(default_factory=dict)
    errors: dict[K, str] = field(default_factory=dict)
    cancelled: bool = False
    stopped_by: str | None = None


def run_batch[K: Hashable, T](
    items: Sequence[K],
    work: Callable[[K], T],
    cancellation: Cancellation,
    on_progress: Callable[[BatchProgress], None] | None = None,
) -> BatchResult[K, T]:
    outcome: BatchResult[K, T] = BatchResult()
    failed = repeats = 0
    previous_error: str | None = None
    for done, item in enumerate(items, start=1):
        if cancellation.cancelled:
            outcome.cancelled = True
            break
        try:
            outcome.results[item] = work(item)
        except AiCancelledError:
            outcome.cancelled = True
            break
        except Exception as error:
            message = str(error) or type(error).__name__
            outcome.errors[item] = message
            failed += 1
            repeats = repeats + 1 if message == previous_error else 1
            previous_error = message
            if not isinstance(error, AiError) or isinstance(error, STOPPING_ERRORS) or repeats >= SAME_ERRORS_IN_A_ROW_TO_STOP:
                outcome.stopped_by = message
        else:
            repeats, previous_error = 0, None
        if on_progress is not None:
            on_progress(BatchProgress(done, failed, len(items)))
        if outcome.stopped_by is not None:
            break
    return outcome
