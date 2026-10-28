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
