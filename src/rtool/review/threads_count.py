from rtool.storage.repositories import Store


def open_thread_counts(store: Store, review_id: int) -> dict[tuple[str, str, str], int]:
    del store, review_id
    return {}
