import os
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from rtool.errors import InvalidRequestError

MAX_ENTRIES = 1000
GIT_DIR = ".git"
HIDDEN_PREFIX = "."


@dataclass(frozen=True)
class DirectoryEntry:
    name: str
    path: str
    is_repo: bool


@dataclass(frozen=True)
class DirectoryListing:
    path: str
    parent: str | None
    home: str
    is_repo: bool
    entries: list[DirectoryEntry]
    truncated: bool


def list_directories(path: str | None) -> DirectoryListing:
    home = Path.home().resolve()
    directory = _resolve(path, home)
    try:
        children = sorted((child for child in directory.iterdir() if _is_visible_directory(child)), key=lambda child: child.name.lower())
    except OSError as error:
        raise InvalidRequestError(f"Cannot read {directory}: {error.strerror or error}") from error
    entries = [DirectoryEntry(child.name, str(child), _is_repo(child)) for child in children[:MAX_ENTRIES]]
    parent = None if directory.parent == directory else str(directory.parent)
    return DirectoryListing(str(directory), parent, str(home), _is_repo(directory), entries, len(children) > MAX_ENTRIES)


def _resolve(path: str | None, home: Path) -> Path:
    if not path:
        return home
    try:
        directory = Path(path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise InvalidRequestError(f"{path} does not exist") from error
    if not directory.is_dir():
        raise InvalidRequestError(f"{path} is not a directory")
    return directory


def _is_visible_directory(path: Path) -> bool:
    try:
        return not path.name.startswith(HIDDEN_PREFIX) and path.is_dir()
    except OSError:
        return False


def _is_repo(path: Path) -> bool:
    try:
        return (path / GIT_DIR).exists()
    except OSError:
        return False


SKIPPED_DIRECTORIES = frozenset(
    {"node_modules", "Library", "Applications", "Pictures", "Music", "Movies", "venv", "__pycache__", "site-packages", "vendor", "dist", "build", "target"}
)


@dataclass(frozen=True)
class ScanLimits:
    max_depth: int = 4
    time_budget_seconds: float = 5.0
    max_results: int = 500


@dataclass(frozen=True)
class FoundRepository:
    name: str
    path: str


@dataclass(frozen=True)
class RepositoryScan:
    root: str
    repositories: list[FoundRepository]
    truncated: bool


def find_repositories(root: Path | None = None, limits: ScanLimits | None = None) -> RepositoryScan:
    start = (root or Path.home()).resolve()
    limits = limits or ScanLimits()
    deadline = time.monotonic() + limits.time_budget_seconds
    found: list[FoundRepository] = []
    pending: deque[tuple[Path, int]] = deque([(start, 0)])
    truncated = False
    while pending:
        if time.monotonic() > deadline or len(found) >= limits.max_results:
            truncated = True
            break
        directory, depth = pending.popleft()
        for child in _scannable_children(directory):
            if _is_repo(child):
                found.append(FoundRepository(child.name, str(child)))
            elif depth + 1 < limits.max_depth:
                pending.append((child, depth + 1))
    return RepositoryScan(str(start), sorted(found, key=lambda repo: repo.path.lower()), truncated)


def _scannable_children(directory: Path) -> list[Path]:
    try:
        with os.scandir(directory) as entries:
            return [
                Path(entry.path)
                for entry in entries
                if not entry.name.startswith(HIDDEN_PREFIX) and entry.name not in SKIPPED_DIRECTORIES and _is_real_directory(entry)
            ]
    except OSError:
        return []


def _is_real_directory(entry: os.DirEntry[str]) -> bool:
    try:
        return entry.is_dir(follow_symlinks=False)
    except OSError:
        return False
