from collections.abc import Callable, Hashable, Sequence
from dataclasses import dataclass, field

from bussola.ai.base import AiCancelledError, AiError, Cancellation


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


def run_batch[K: Hashable, T](
    items: Sequence[K],
    work: Callable[[K], T],
    cancellation: Cancellation,
    on_progress: Callable[[BatchProgress], None] | None = None,
) -> BatchResult[K, T]:
    outcome: BatchResult[K, T] = BatchResult()
    for item in items:
        if cancellation.cancelled:
            outcome.cancelled = True
            break
        try:
            outcome.results[item] = work(item)
        except AiCancelledError:
            outcome.cancelled = True
            break
        except AiError as error:
            outcome.errors[item] = str(error)
        if on_progress is not None:
            on_progress(BatchProgress(len(outcome.results) + len(outcome.errors), len(outcome.errors), len(items)))
    return outcome
