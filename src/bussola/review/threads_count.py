from collections.abc import Iterable

from bussola.review.keys import KeyTuple
from bussola.review.thread_types import ThreadScope, ThreadStatus
from bussola.storage.models import Thread


def open_thread_counts(threads: Iterable[Thread]) -> dict[KeyTuple | None, int]:
    counts: dict[KeyTuple | None, int] = {}
    for thread in threads:
        if thread.status != ThreadStatus.OPEN:
            continue
        key = None
        if thread.scope == ThreadScope.UNIT and thread.path is not None and thread.kind is not None and thread.qualified_name is not None:
            key = (thread.path, thread.kind, thread.qualified_name)
        counts[key] = counts.get(key, 0) + 1
    return counts
