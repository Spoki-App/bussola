from enum import StrEnum


class ThreadScope(StrEnum):
    REVIEW = "review"
    FILE = "file"
    UNIT = "unit"


class ThreadStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


def is_resolvable(scope: str) -> bool:
    return scope != ThreadScope.REVIEW
