from enum import StrEnum


class ThreadScope(StrEnum):
    REVIEW = "review"
    FILE = "file"
    UNIT = "unit"


class ThreadStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
