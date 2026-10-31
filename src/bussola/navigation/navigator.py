from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from bussola.git import GitRepo
from bussola.navigation.index import IndexCache, Starter, SymbolIndex, start_daemon
from bussola.navigation.lsp import ServerLocation
from bussola.navigation.positions import byte_to_utf16, preview, source_lines, utf16_to_byte
from bussola.navigation.servers import LanguageServers, server_command
from bussola.navigation.specs import SERVER_SPECS, ServerSpec
from bussola.navigation.symbols import SourceLanguage, Symbol, language_for, references, symbol_at

MAX_TARGETS = 200
CHECKOUTS_DIR = "checkouts"


class Origin(StrEnum):
    DEFINITION = "definition"
    REFERENCE = "reference"


class TargetRole(StrEnum):
    DEFINITION = "definition"
    USAGE = "usage"


class Resolver(StrEnum):
    TREE_SITTER = "tree-sitter"
    LANGUAGE_SERVER = "language-server"


@dataclass(frozen=True)
class Target:
    role: TargetRole
    path: str
    line: int
    column: int
    preview: str


@dataclass(frozen=True)
class Navigation:
    ready: bool
    symbol: str | None = None
    origin: Origin | None = None
    resolver: Resolver = Resolver.TREE_SITTER
    targets: tuple[Target, ...] = ()
    missing_server: ServerSpec | None = None


@dataclass(frozen=True)
class Click:
    path: str
    line: int
    column: int


class SourceFiles:
    def __init__(self, repo: GitRepo, commit: str) -> None:
        self._repo = repo
        self._commit = commit
        self._lines: dict[str, list[bytes]] = {}

    def lines(self, path: str) -> list[bytes]:
        if path not in self._lines:
            self._lines[path] = source_lines(self._repo.file_at(self._commit, path) or b"")
        return self._lines[path]

    def target(self, role: TargetRole, path: str, row: int, byte_column: int) -> Target | None:
        lines = self.lines(path)
        if row >= len(lines):
            return None
        return Target(role, path, row + 1, byte_to_utf16(lines[row], byte_column), preview(lines[row]))

    def server_target(self, role: TargetRole, location: ServerLocation) -> Target | None:
        lines = self.lines(location.path)
        if location.row >= len(lines):
            return None
        return Target(role, location.path, location.row + 1, location.character, preview(lines[location.row]))


class Navigator:
    def __init__(self, data_dir: Path, start: Starter = start_daemon) -> None:
        self.indexes = IndexCache(start)
        self.servers = LanguageServers(data_dir / CHECKOUTS_DIR, start)

    def prepare(self, repo: GitRepo, commit: str, ignore: tuple[str, ...]) -> bool:
        return self.indexes.get(repo, commit, ignore) is not None

    def navigate(self, repo: GitRepo, commit: str, ignore: tuple[str, ...], click: Click) -> Navigation:
        language = language_for(click.path)
        source = repo.file_at(commit, click.path)
        if language is None or source is None:
            return Navigation(ready=True)
        lines = source_lines(source)
        if not 1 <= click.line <= len(lines):
            return Navigation(ready=True)
        symbol = symbol_at(language, source, click.line - 1, utf16_to_byte(lines[click.line - 1], click.column))
        if symbol is None:
            return Navigation(ready=True)
        origin = Origin.DEFINITION if symbol.definition else Origin.REFERENCE
        spec = SERVER_SPECS[language.family]
        missing = spec if server_command(spec) is None else None
        files = SourceFiles(repo, commit)
        position = ServerLocation(click.path, symbol.row, byte_to_utf16(lines[symbol.row], symbol.start))
        role, locations = self._ask_server(repo, commit, spec, position, origin)
        from_server = tuple(target for location in locations if (target := files.server_target(role, location)) is not None)
        if from_server:
            return Navigation(True, symbol.name, origin, Resolver.LANGUAGE_SERVER, from_server, missing)
        index = self.indexes.get(repo, commit, ignore)
        if index is None:
            return Navigation(False, symbol.name, origin, missing_server=missing)
        targets = _usages(index, language, symbol, files) if origin == Origin.DEFINITION else _definitions(index, language, symbol, click.path, files)
        return Navigation(True, symbol.name, origin, Resolver.TREE_SITTER, targets, missing)

    def close(self) -> None:
        self.servers.close()

    def _ask_server(self, repo: GitRepo, commit: str, spec: ServerSpec, position: ServerLocation, origin: Origin) -> tuple[TargetRole, list[ServerLocation]]:
        if origin == Origin.DEFINITION:
            role, locations = TargetRole.USAGE, self.servers.references(repo, commit, spec, position)
        else:
            role, locations = TargetRole.DEFINITION, self.servers.definitions(repo, commit, spec, position)
        ordered = sorted(set(locations or []), key=lambda location: (location.path, location.row, location.character))
        return role, ordered[:MAX_TARGETS]


def _definitions(index: SymbolIndex, language: SourceLanguage, symbol: Symbol, path: str, files: SourceFiles) -> tuple[Target, ...]:
    found = sorted(index.definitions(language.family, symbol.name), key=lambda item: (item[0].path != path, item[0].path, item[1].row))
    return tuple(
        target for file, definition in found[:MAX_TARGETS] if (target := files.target(TargetRole.DEFINITION, file.path, definition.row, definition.start))
    )


def _usages(index: SymbolIndex, language: SourceLanguage, symbol: Symbol, files: SourceFiles) -> tuple[Target, ...]:
    targets: list[Target] = []
    for file in index.files_using(language.family, symbol.name):
        file_language = language_for(file.path) or language
        source = b"\n".join(files.lines(file.path))
        for usage in references(file_language, source, symbol.name):
            target = files.target(TargetRole.USAGE, file.path, usage.row, usage.start)
            if target is not None:
                targets.append(target)
            if len(targets) >= MAX_TARGETS:
                return tuple(targets)
    return tuple(targets)
