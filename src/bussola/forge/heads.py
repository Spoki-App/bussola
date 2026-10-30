from bussola.errors import ConflictError

SHORT_SHA = 8


class HeadMismatchError(ConflictError):
    pass


def head_mismatch(pull_head: str, reviewed_head: str) -> str | None:
    if pull_head == reviewed_head:
        return None
    return f"The pull request head ({pull_head[:SHORT_SHA]}) differs from the reviewed head ({reviewed_head[:SHORT_SHA]})."
