from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass, field

from bussola.ai.base import AiCancelledError, AiNotConfiguredError, AiTargetChangedError, AiTimeoutError, AiUnreachableError, Cancellation

TIMEOUTS_IN_A_ROW_TO_STOP = 2


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
    failed = timeouts_in_a_row = 0
    for done, item in enumerate(items, start=1):
        if cancellation.cancelled:
            outcome.cancelled = True
            break
        try:
            outcome.results[item] = work(item)
            timeouts_in_a_row = 0
        except AiCancelledError:
            outcome.cancelled = True
            break
        except (AiNotConfiguredError, AiTargetChangedError, AiUnreachableError) as error:
            outcome.stopped_by = str(error)
            break
        except AiTimeoutError as error:
            outcome.errors[item] = str(error)
            failed += 1
            timeouts_in_a_row += 1
            if timeouts_in_a_row >= TIMEOUTS_IN_A_ROW_TO_STOP:
                outcome.stopped_by = str(error)
                break
        except Exception as error:
            outcome.errors[item] = str(error) or type(error).__name__
            failed += 1
        if on_progress is not None:
            on_progress(BatchProgress(done, failed, len(items)))
    return outcome
