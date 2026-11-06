from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Self

from tree_sitter import Node, Tree

from bussola.git import BlobReader, GitRepo
from bussola.navigation.definitions import CODE_LANGUAGES, HoverDoc, from_hover
from bussola.navigation.external import Imported, LibrarySource, ProjectLayout, imported_symbol, is_library_file, package_info
from bussola.navigation.index import MAX_FILE_BYTES, IndexCache, IndexedFile, Starter, SymbolIndex, start_daemon
from bussola.navigation.lsp import ServerLocation
from bussola.navigation.positions import byte_to_utf16, preview, source_lines, utf16_to_byte
from bussola.navigation.scopes import Enclosing, enclosing_at
from bussola.navigation.servers import LanguageServers, server_command
from bussola.navigation.specs import SERVER_SPECS, ServerSpec
from bussola.navigation.symbols import SourceLanguage, Symbol, identifier_at, is_member, language_for, references, symbol_of
from bussola.navigation.symbols import parse as parse_source
from bussola.units.extractors.treesitter import parse

MAX_TARGETS = 200
CHECKOUTS_DIR = "checkouts"
CACHED_LAYOUTS = 4


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
    enclosing: Enclosing | None


@dataclass(frozen=True)
class Documentation:
    qualified_name: str
    package: str
    version: str | None
    url: str | None
    home_url: str | None
    signature: str | None
    language: str
    docstring: str | None
    source: LibrarySource | None


@dataclass(frozen=True)
class Navigation:
    ready: bool
    symbol: str | None = None
    origin: Origin | None = None
    resolver: Resolver = Resolver.TREE_SITTER
    targets: tuple[Target, ...] = ()
    missing_server: ServerSpec | None = None
    documentation: Documentation | None = None


@dataclass(frozen=True)
class Click:
    path: str
    line: int
    column: int


class SourceFiles:
    def __init__(self, repo: GitRepo, commit: str) -> None:
        self._repo = repo
        self._commit = commit
        self._reader: BlobReader | None = None
        self._sources: dict[str, bytes] = {}
        self._lines: dict[str, list[bytes]] = {}
        self._trees: dict[str, Tree | None] = {}

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_: object) -> None:
        if self._reader is not None:
            self._reader.close()

    def seed(self, path: str, source: bytes) -> None:
        self._sources[path] = source

    def source(self, path: str, object_id: str | None = None) -> bytes:
        if path not in self._sources:
            self._sources[path] = self._blob(object_id) if object_id else self._repo.file_at(self._commit, path) or b""
        return self._sources[path]

    def lines(self, path: str) -> list[bytes]:
        if path not in self._lines:
            self._lines[path] = source_lines(self.source(path))
        return self._lines[path]

    def target(self, role: TargetRole, location: ServerLocation) -> Target | None:
        lines = self.lines(location.path)
        if location.row >= len(lines):
            return None
        enclosing = self.enclosing(location.path, location.row, utf16_to_byte(lines[location.row], location.character)) if role == TargetRole.USAGE else None
        return Target(role, location.path, location.row + 1, location.character, preview(lines[location.row]), enclosing)

    def enclosing(self, path: str, row: int, column: int) -> Enclosing | None:
        language = language_for(path)
        if language is None:
            return None
        if path not in self._trees:
            source = self.source(path)
            self._trees[path] = parse(language.grammar, source) if len(source) <= MAX_FILE_BYTES else None
        tree = self._trees[path]
        return enclosing_at(language.family, tree.root_node, row, column) if tree else None

    def symbol_target(self, role: TargetRole, file: IndexedFile, symbol: Symbol) -> Target | None:
        self.source(file.path, file.object_id)
        lines = self.lines(file.path)
        column = byte_to_utf16(lines[symbol.row], symbol.start) if symbol.row < len(lines) else 0
        return self.target(role, ServerLocation(file.path, symbol.row, column))

    def _blob(self, object_id: str) -> bytes:
        if self._reader is None:
            self._reader = self._repo.blob_reader()
        return self._reader.read(object_id)


class Navigator:
    def __init__(self, data_dir: Path, start: Starter = start_daemon) -> None:
        self.indexes = IndexCache(start)
        self.servers = LanguageServers(data_dir / CHECKOUTS_DIR, start)

    def prepare(self, repo: GitRepo, commit: str, ignore: tuple[str, ...]) -> bool:
        return self.indexes.get(repo, commit, ignore) is not None

    def navigate(self, repo: GitRepo, commit: str, ignore: tuple[str, ...], click: Click) -> Navigation:
        clicked = _clicked(repo, commit, click)
        if clicked is None:
            return Navigation(ready=True)
        language, source, lines, tree, node = clicked
        symbol = symbol_of(language, node)
        origin = Origin.DEFINITION if symbol.definition else Origin.REFERENCE
        spec = SERVER_SPECS[language.family]
        missing = spec if server_command(spec) is None else None
        position = ServerLocation(click.path, symbol.row, byte_to_utf16(lines[symbol.row], symbol.start))
        imported = imported_symbol(language, tree, node) if origin == Origin.REFERENCE else None
        if imported is not None and _layout(repo.root, commit).is_external(imported):
            documentation, resolver = self._document(repo, commit, spec, position, imported)
            return Navigation(True, symbol.name, origin, resolver, missing_server=missing, documentation=documentation)
        with SourceFiles(repo, commit) as files:
            files.seed(click.path, source)
            role, locations = self._ask_server(repo, commit, spec, position, origin)
            from_server = tuple(target for location in locations if (target := files.target(role, location)) is not None)
            if from_server:
                return Navigation(True, symbol.name, origin, Resolver.LANGUAGE_SERVER, from_server, missing)
            index = self.indexes.get(repo, commit, ignore)
            if index is None:
                return Navigation(False, symbol.name, origin, missing_server=missing)
            targets = _usages(index, language, symbol, files) if origin == Origin.DEFINITION else _definitions(index, language, node, click.path, files)
            return Navigation(True, symbol.name, origin, Resolver.TREE_SITTER, targets, missing)

    def close(self) -> None:
        self.servers.close()

    def _document(self, repo: GitRepo, commit: str, spec: ServerSpec, position: ServerLocation, imported: Imported) -> tuple[Documentation, Resolver]:
        text = self.servers.ask(repo, commit, spec, lambda session: session.hover(position.path, position.row, position.character), None)
        hover = from_hover(text) if text else HoverDoc(None, None, None)
        package = package_info(imported, repo.root, str(Path(position.path).parent), _layout(repo.root, commit))
        local = package.definition
        source = LibrarySource(str(local.path), local.line) if local is not None and is_library_file(local.path, repo.root) else None
        documentation = Documentation(
            qualified_name=imported.qualified_name,
            package=package.name,
            version=package.version,
            url=package.url,
            home_url=package.home_url,
            signature=hover.signature or (local.signature if local else None),
            language=(hover.language if hover.signature else None) or CODE_LANGUAGES[imported.family],
            docstring=hover.docstring or (local.docstring if local else None),
            source=source,
        )
        return documentation, Resolver.LANGUAGE_SERVER if hover.signature or hover.docstring else Resolver.TREE_SITTER

    def _ask_server(self, repo: GitRepo, commit: str, spec: ServerSpec, position: ServerLocation, origin: Origin) -> tuple[TargetRole, list[ServerLocation]]:
        if origin == Origin.DEFINITION:
            role = TargetRole.USAGE
            locations = self.servers.ask(repo, commit, spec, lambda session: session.references(position.path, position.row, position.character), [])
        else:
            role = TargetRole.DEFINITION
            locations = self.servers.ask(repo, commit, spec, lambda session: session.definitions(position.path, position.row, position.character), [])
        ordered = sorted(set(locations), key=lambda location: (location.path, location.row, location.character))
        return role, ordered[:MAX_TARGETS]


def _clicked(repo: GitRepo, commit: str, click: Click) -> tuple[SourceLanguage, bytes, list[bytes], Tree, Node] | None:
    language = language_for(click.path)
    source = repo.file_at(commit, click.path)
    lines = source_lines(source) if source is not None else []
    if language is None or source is None or not 1 <= click.line <= len(lines):
        return None
    tree = parse_source(language, source)
    node = identifier_at(language, tree, click.line - 1, utf16_to_byte(lines[click.line - 1], click.column))
    return (language, source, lines, tree, node) if node is not None else None


@lru_cache(maxsize=CACHED_LAYOUTS)
def _layout(root: Path, commit: str) -> ProjectLayout:
    repo = GitRepo(root)
    blobs = {blob.path: blob.object_id for blob in repo.tree_blobs(commit) if not blob.is_symlink}
    with repo.blob_reader() as reader:
        return ProjectLayout.of(list(blobs), lambda path: reader.read(blobs[path]))


def _definitions(index: SymbolIndex, language: SourceLanguage, node: Node, path: str, files: SourceFiles) -> tuple[Target, ...]:
    symbol = symbol_of(language, node)
    found = sorted(index.definitions(language.family, symbol.name), key=lambda item: (item[0].path != path, item[0].path, item[1].row))
    local = [item for item in found if item[0].path == path]
    if local and not is_member(node):
        found = local
    return tuple(target for file, definition in found[:MAX_TARGETS] if (target := files.symbol_target(TargetRole.DEFINITION, file, definition)))


def _usages(index: SymbolIndex, language: SourceLanguage, symbol: Symbol, files: SourceFiles) -> tuple[Target, ...]:
    targets: list[Target] = []
    for file in index.files_using(language.family, symbol.name):
        source = files.source(file.path, file.object_id)
        for usage in references(language_for(file.path) or language, source, symbol.name):
            target = files.symbol_target(TargetRole.USAGE, file, usage)
            if target is not None:
                targets.append(target)
            if len(targets) >= MAX_TARGETS:
                return tuple(targets)
    return tuple(targets)
