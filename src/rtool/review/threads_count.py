from rtool.review.anchoring import OPEN_STATUS, UNIT_SCOPE
from rtool.storage.repositories import Store

type ThreadKey = tuple[str, str, str]


def open_thread_counts(store: Store, review_id: int) -> dict[ThreadKey | None, int]:
    counts: dict[ThreadKey | None, int] = {}
    for thread in store.threads.threads(review_id):
        if thread.status != OPEN_STATUS:
            continue
        key = None
        if thread.scope == UNIT_SCOPE and thread.path is not None and thread.kind is not None and thread.qualified_name is not None:
            key = (thread.path, thread.kind, thread.qualified_name)
        counts[key] = counts.get(key, 0) + 1
    return counts
