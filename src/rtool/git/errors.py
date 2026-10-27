class GitError(Exception):
    def __init__(self, command: list[str], stderr: str) -> None:
        super().__init__(f"git {' '.join(command)} failed: {stderr.strip()}")
        self.command = command
        self.stderr = stderr


class InvalidRefError(ValueError):
    def __init__(self, ref: str) -> None:
        super().__init__(f"Not a valid commit reference: {ref!r}")
        self.ref = ref
