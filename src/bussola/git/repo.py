import os
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Self

from bussola.git.blobs import OBJECT_ID, BlobReader
from bussola.git.errors import GitError, InvalidRefError

GIT = "git"
SUBMODULE_MODE = "160000"
BLOB_TYPE = "blob"
RAW_RECORD_PREFIX = ":"
DEFAULT_REMOTE = "origin"
LOCAL_PREFIX = "refs/heads/"
REMOTE_PREFIX = "refs/remotes/"
SYMBOLIC_HEAD = "/HEAD"
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
        self._remotes: list[str] | None = None

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

    def remotes(self) -> list[str]:
        if self._remotes is None:
            self._remotes = self.run("remote").decode().split()
        return self._remotes

    def upstream_remote(self, ref: str) -> str | None:
        remotes = self.remotes()
        prefix = next((remote for remote in remotes if ref.startswith(f"{remote}/")), None)
        if prefix is not None:
            return prefix
        try:
            upstream = self.run("rev-parse", "--abbrev-ref", "--symbolic-full-name", "--end-of-options", f"{ref}@{{upstream}}").decode().strip()
        except GitError:
            return DEFAULT_REMOTE if DEFAULT_REMOTE in remotes else None
        return next((remote for remote in remotes if upstream.startswith(f"{remote}/")), None)

    def remote_url(self, remote: str) -> str | None:
        if remote not in self.remotes():
            return None
        return self.config_value(f"remote.{remote}.url")

    def fetch_refspecs(self, remote: str, refspecs: list[str]) -> None:
        if remote not in self.remotes():
            raise InvalidRefError(remote)
        self.run("fetch", "--quiet", "--no-tags", "--end-of-options", remote, *refspecs)

    def is_valid_branch_name(self, name: str) -> bool:
        try:
            self.run("check-ref-format", "--branch", name)
        except GitError:
            return False
        return not name.startswith("-")

    def fetch(self, remote: str) -> None:
        if remote not in self.remotes():
            raise InvalidRefError(remote)
        self.run("fetch", "--prune", "--quiet", "--end-of-options", remote)

    def branches(self) -> tuple[list[str], list[str]]:
        output = self.run("for-each-ref", "--format=%(refname)", "refs/heads", "refs/remotes").decode().split("\n")
        local = sorted(ref.removeprefix(LOCAL_PREFIX) for ref in output if ref.startswith(LOCAL_PREFIX))
        remote = sorted(ref.removeprefix(REMOTE_PREFIX) for ref in output if ref.startswith(REMOTE_PREFIX) and not ref.endswith(SYMBOLIC_HEAD))
        return local, remote

    def config_value(self, key: str) -> str | None:
        return read_git_config(self.root, key)

    def file_at(self, commit: str, path: str) -> bytes | None:
        if not OBJECT_ID.fullmatch(commit):
            raise InvalidRefError(commit)
        try:
            return self.run("cat-file", "blob", f"{commit}:{path}")
        except GitError:
            return None

    def tree_paths(self, commit: str) -> list[str]:
        if not OBJECT_ID.fullmatch(commit):
            raise InvalidRefError(commit)
        return [path for path in self.run("ls-tree", "-r", "--name-only", "-z", commit).decode(errors="replace").split("\0") if path]

    def tree_blobs(self, commit: str) -> list[BlobRef]:
        if not OBJECT_ID.fullmatch(commit):
            raise InvalidRefError(commit)
        entries = self.run("ls-tree", "-r", "-z", "--full-tree", commit).decode(errors="surrogateescape").split("\0")
        return [_tree_entry(entry) for entry in entries if entry and _is_blob_entry(entry)]

    def archive(self, commit: str, output: Path) -> None:
        if not OBJECT_ID.fullmatch(commit):
            raise InvalidRefError(commit)
        self.run("archive", "--format=tar", f"--output={output}", commit)

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


def _is_blob_entry(entry: str) -> bool:
    return entry.split(" ", 2)[1] == BLOB_TYPE


def _tree_entry(entry: str) -> BlobRef:
    meta, _, path = entry.partition("\t")
    mode, _, object_id = meta.split(" ")
    return BlobRef(path, object_id, mode)


def read_git_config(cwd: Path, key: str) -> str | None:
    result = subprocess.run([GIT, "config", "--get", key], cwd=cwd, env=_git_env(), capture_output=True, check=False)
    value = result.stdout.decode(errors="replace").strip()
    return value if result.returncode == 0 and value else None


def read_git_config_values(cwd: Path, pattern: str) -> dict[str, str]:
    result = subprocess.run([GIT, "config", "--get-regexp", pattern], cwd=cwd, env=_git_env(), capture_output=True, check=False)
    values: dict[str, str] = {}
    for line in result.stdout.decode(errors="replace").splitlines():
        key, _, value = line.partition(" ")
        if value.strip():
            values[key] = value.strip()
    return values


def _git_env() -> dict[str, str]:
    return {**os.environ, **GIT_ENV}


def _run_git(cwd: Path, args: list[str]) -> bytes:
    result = subprocess.run([GIT, *args], cwd=cwd, env=_git_env(), capture_output=True, check=False)
    if result.returncode != 0:
        raise GitError(args, result.stderr.decode(errors="replace"))
    return result.stdout
