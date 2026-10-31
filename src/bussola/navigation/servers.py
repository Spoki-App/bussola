import shutil
import tarfile
import tempfile
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from bussola.git import GitError, GitRepo
from bussola.navigation.index import Starter, start_daemon
from bussola.navigation.lsp import LanguageServerError, LanguageServerSession, ServerLocation
from bussola.navigation.specs import ServerSpec

CACHED_SESSIONS = 3
STAGING_PREFIX = ".staging-"
ARCHIVE_SUFFIX = ".tar"

type SessionKey = tuple[Path, str, str]


def server_command(spec: ServerSpec) -> list[str] | None:
    for executable, *args in spec.commands:
        found = shutil.which(executable)
        if found is not None:
            return [found, *args]
    return None


@dataclass
class _Slot:
    session: LanguageServerSession | None = None
    failed: bool = False


class LanguageServers:
    def __init__(self, checkouts: Path, start: Starter = start_daemon, capacity: int = CACHED_SESSIONS) -> None:
        self._checkouts = checkouts
        self._start = start
        self._capacity = capacity
        self._lock = threading.Lock()
        self._checkout_lock = threading.Lock()
        self._slots: OrderedDict[SessionKey, _Slot] = OrderedDict()
        self._cleaned = False

    def definitions(self, repo: GitRepo, commit: str, spec: ServerSpec, position: ServerLocation) -> list[ServerLocation] | None:
        session = self._session(repo, commit, spec)
        if session is None:
            return None
        try:
            return session.definitions(position.path, position.row, position.character)
        except (LanguageServerError, OSError):
            return None

    def references(self, repo: GitRepo, commit: str, spec: ServerSpec, position: ServerLocation) -> list[ServerLocation] | None:
        session = self._session(repo, commit, spec)
        if session is None:
            return None
        try:
            return session.references(position.path, position.row, position.character)
        except (LanguageServerError, OSError):
            return None

    def checkout(self, commit: str) -> Path:
        return (self._checkouts / commit).resolve()

    def close(self) -> None:
        with self._lock:
            slots = list(self._slots.values())
            self._slots.clear()
        for slot in slots:
            if slot.session is not None:
                slot.session.close()
        shutil.rmtree(self._checkouts, ignore_errors=True)

    def _session(self, repo: GitRepo, commit: str, spec: ServerSpec) -> LanguageServerSession | None:
        command = server_command(spec)
        if command is None:
            return None
        key = (repo.root, commit, spec.family)
        with self._lock:
            slot = self._slots.get(key)
            if slot is not None:
                self._slots.move_to_end(key)
                return slot.session
            slot = _Slot()
            self._slots[key] = slot
        self._start(lambda: self._open(slot, repo, commit, spec, command))
        return slot.session

    def _open(self, slot: _Slot, repo: GitRepo, commit: str, spec: ServerSpec, command: list[str]) -> None:
        try:
            slot.session = LanguageServerSession.open(command, self._prepare_checkout(repo, commit), spec)
        except (LanguageServerError, GitError, OSError, tarfile.TarError):
            slot.failed = True
        self._evict()

    def _evict(self) -> None:
        with self._lock:
            evicted: list[tuple[SessionKey, _Slot]] = []
            for key, slot in list(self._slots.items()):
                if len(self._slots) <= self._capacity:
                    break
                if slot.session is not None or slot.failed:
                    evicted.append((key, slot))
                    del self._slots[key]
            commits_in_use = {commit for _, commit, _ in self._slots}
        for (_, commit, _), slot in evicted:
            if slot.session is not None:
                slot.session.close()
            if commit not in commits_in_use:
                shutil.rmtree(self.checkout(commit), ignore_errors=True)

    def _prepare_checkout(self, repo: GitRepo, commit: str) -> Path:
        with self._checkout_lock:
            if not self._cleaned:
                shutil.rmtree(self._checkouts, ignore_errors=True)
                self._cleaned = True
            target = self.checkout(commit)
            if target.is_dir():
                return target
            self._checkouts.mkdir(parents=True, exist_ok=True)
            staging = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=self._checkouts))
            archive = staging.with_suffix(ARCHIVE_SUFFIX)
            try:
                repo.archive(commit, archive)
                with tarfile.open(archive) as tar:
                    tar.extractall(staging, filter="data")
                staging.rename(target)
            finally:
                archive.unlink(missing_ok=True)
                shutil.rmtree(staging, ignore_errors=True)
            return target
