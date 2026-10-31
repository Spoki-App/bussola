import threading
from collections import OrderedDict, defaultdict
from collections.abc import Callable, Mapping
from concurrent.futures import Future
from dataclasses import dataclass, replace
from pathlib import Path

from bussola.git import GitRepo
from bussola.globs import matches_any
from bussola.navigation.symbols import Symbol, file_symbols, language_for

MAX_FILE_BYTES = 1_000_000
SYMLINK_MODE = "120000"
CACHED_INDEXES = 4

type Starter = Callable[[Callable[[], None]], None]
type IndexKey = tuple[Path, str]
type NameKey = tuple[str, str]


@dataclass(frozen=True)
class IndexedFile:
    path: str
    object_id: str
    family: str
    definitions: tuple[Symbol, ...]
    used_names: tuple[str, ...]


class SymbolIndex:
    def __init__(self, commit: str, files: list[IndexedFile]) -> None:
        self.commit = commit
        self.files = {file.path: file for file in files}
        self._definitions: dict[NameKey, list[tuple[IndexedFile, Symbol]]] = defaultdict(list)
        self._users: dict[NameKey, list[IndexedFile]] = defaultdict(list)
        for file in files:
            for symbol in file.definitions:
                self._definitions[file.family, symbol.name].append((file, symbol))
            for name in file.used_names:
                self._users[file.family, name].append(file)

    def definitions(self, family: str, name: str) -> list[tuple[IndexedFile, Symbol]]:
        return list(self._definitions.get((family, name), []))

    def files_using(self, family: str, name: str) -> list[IndexedFile]:
        return sorted(self._users.get((family, name), []), key=lambda file: file.path)


def build_index(repo: GitRepo, commit: str, ignore: tuple[str, ...], reuse: Mapping[tuple[str, str], IndexedFile]) -> SymbolIndex:
    blobs = [blob for blob in repo.tree_blobs(commit) if blob.mode != SYMLINK_MODE and not blob.is_submodule and not matches_any(blob.path, ignore)]
    files: list[IndexedFile] = []
    with repo.blob_reader() as reader:
        for blob in blobs:
            language = language_for(blob.path)
            if language is None:
                continue
            previous = reuse.get((blob.object_id, language.family))
            if previous is not None:
                files.append(replace(previous, path=blob.path))
                continue
            source = reader.read(blob.object_id)
            if len(source) > MAX_FILE_BYTES:
                continue
            symbols = file_symbols(language, source)
            files.append(IndexedFile(blob.path, blob.object_id, language.family, symbols.definitions, symbols.used_names))
    return SymbolIndex(commit, files)


def start_daemon(task: Callable[[], None]) -> None:
    threading.Thread(target=task, name="bussola-navigation", daemon=True).start()


class IndexCache:
    def __init__(self, start: Starter = start_daemon, capacity: int = CACHED_INDEXES) -> None:
        self._start = start
        self._capacity = capacity
        self._lock = threading.Lock()
        self._ready: OrderedDict[IndexKey, SymbolIndex] = OrderedDict()
        self._building: dict[IndexKey, Future[SymbolIndex]] = {}

    def get(self, repo: GitRepo, commit: str, ignore: tuple[str, ...]) -> SymbolIndex | None:
        key = (repo.root, commit)
        with self._lock:
            index = self._ready.get(key)
            if index is not None:
                self._ready.move_to_end(key)
                return index
            building = self._building.get(key)
            if building is not None:
                return self._finished(key, building)
            future: Future[SymbolIndex] = Future()
            self._building[key] = future
            reuse = {(file.object_id, file.family): file for cached in self._ready.values() for file in cached.files.values()}
        self._start(lambda: self._build(future, repo, commit, ignore, reuse))
        with self._lock:
            return self._finished(key, future) if future.done() else None

    def _build(self, future: Future[SymbolIndex], repo: GitRepo, commit: str, ignore: tuple[str, ...], reuse: Mapping[tuple[str, str], IndexedFile]) -> None:
        try:
            future.set_result(build_index(repo, commit, ignore, reuse))
        except Exception as error:
            future.set_exception(error)

    def _finished(self, key: IndexKey, future: Future[SymbolIndex]) -> SymbolIndex | None:
        if not future.done():
            return None
        del self._building[key]
        index = future.result()
        self._ready[key] = index
        while len(self._ready) > self._capacity:
            self._ready.popitem(last=False)
        return index
