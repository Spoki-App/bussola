import re
import subprocess
from types import TracebackType
from typing import IO, Self

from rtool.git.errors import GitError

OBJECT_ID = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
MISSING_SUFFIX = b" missing"


class BlobReader:
    def __init__(self, process: subprocess.Popen[bytes]) -> None:
        self._process = process

    def read(self, object_id: str) -> bytes:
        if not OBJECT_ID.fullmatch(object_id):
            raise ValueError(f"Not an object id: {object_id!r}")
        stdin, stdout = self._pipes()
        stdin.write(f"{object_id}\n".encode())
        stdin.flush()
        header = stdout.readline().rstrip(b"\n")
        if not header or header.endswith(MISSING_SUFFIX):
            raise GitError(["cat-file", "--batch"], f"object {object_id} is missing")
        size = int(header.rsplit(b" ", 1)[1])
        data = stdout.read(size)
        stdout.read(1)
        return data

    def close(self) -> None:
        stdin, _ = self._pipes()
        stdin.close()
        self._process.wait()

    def _pipes(self) -> tuple[IO[bytes], IO[bytes]]:
        if self._process.stdin is None or self._process.stdout is None:
            raise RuntimeError("cat-file process has no pipes")
        return self._process.stdin, self._process.stdout

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None) -> None:
        self.close()
