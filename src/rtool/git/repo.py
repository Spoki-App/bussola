import os
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Self

from rtool.git.blobs import BlobReader
from rtool.git.errors import GitError, InvalidRefError

GIT = "git"
SUBMODULE_MODE = "160000"
RAW_RECORD_PREFIX = ":"
GIT_ENV = {"GIT_TERMINAL_PROMPT": "0", "LC_ALL": "C", "GIT_OPTIONAL_LOCKS": "0"}


class ChangeStatus(StrEnum):
    ADDED = "A"
    MODIFIED = "M"
    DELETED = "D"
    RENAMED = "R"
    COPIED = "C"
    TYPE_CHANGED = "T"


@dataclass(frozen=True)
class BlobRef:
    path: str
    object_id: str
    mode: str

    @property
    def is_submodule(self) -> bool:
        return self.mode == SUBMODULE_MODE


@dataclass(frozen=True)
class FileChange:
    status: ChangeStatus
    old: BlobRef | None
    new: BlobRef | None

    @property
    def path(self) -> str:
        ref = self.new or self.old
        if ref is None:
            raise ValueError("FileChange without blobs")
        return ref.path


class GitRepo:
    def __init__(self, root: Path) -> None:
        self.root = root

    @classmethod
    def discover(cls, path: Path) -> Self:
        output = _run_git(path, ["rev-parse", "--show-toplevel"])
        return cls(Path(output.decode().strip()))

    def run(self, *args: str) -> bytes:
        return _run_git(self.root, list(args))

    def resolve_commit(self, ref: str) -> str:
        if not ref or ref.startswith("-") or any(char in ref for char in "\0\n\r"):
            raise InvalidRefError(ref)
        try:
            output = self.run("rev-parse", "--verify", "--quiet", "--end-of-options", f"{ref}^{{commit}}")
        except GitError as error:
            raise InvalidRefError(ref) from error
        return output.decode().strip()

    def merge_base(self, first: str, second: str) -> str:
        return self.run("merge-base", self.resolve_commit(first), self.resolve_commit(second)).decode().strip()

    def first_commit(self) -> str:
        return self.run("rev-list", "--max-parents=0", "HEAD").decode().split()[0]

    def changed_files(self, base: str, head: str) -> list[FileChange]:
        output = self.run("diff", "--no-color", "--no-ext-diff", "--raw", "-z", "-M", "--no-abbrev", self.resolve_commit(base), self.resolve_commit(head))
        return parse_raw_diff(output.decode("utf-8", errors="surrogateescape"))

    def blob_reader(self) -> BlobReader:
        process = subprocess.Popen([GIT, "cat-file", "--batch"], cwd=self.root, env=_git_env(), stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        return BlobReader(process)


def parse_raw_diff(output: str) -> list[FileChange]:
    fields = output.split("\0")
    changes: list[FileChange] = []
    index = 0
    while index < len(fields) and fields[index].startswith(RAW_RECORD_PREFIX):
        old_mode, new_mode, old_id, new_id, status_field = fields[index][1:].split(" ")
        status = ChangeStatus(status_field[0])
        has_two_paths = status in {ChangeStatus.RENAMED, ChangeStatus.COPIED}
        old_path = fields[index + 1]
        new_path = fields[index + 2] if has_two_paths else old_path
        index += 3 if has_two_paths else 2
        old = None if status == ChangeStatus.ADDED else BlobRef(old_path, old_id, old_mode)
        new = None if status == ChangeStatus.DELETED else BlobRef(new_path, new_id, new_mode)
        changes.append(FileChange(status, old, new))
    return changes


def _git_env() -> dict[str, str]:
    return {**os.environ, **GIT_ENV}


def _run_git(cwd: Path, args: list[str]) -> bytes:
    result = subprocess.run([GIT, *args], cwd=cwd, env=_git_env(), capture_output=True, check=False)
    if result.returncode != 0:
        raise GitError(args, result.stderr.decode(errors="replace"))
    return result.stdout
