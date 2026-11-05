import json
import os
import re
import shutil
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import Distribution, distributions
from pathlib import Path, PurePosixPath
from typing import Any, cast

from tree_sitter import Node

from bussola.navigation.symbols import SourceLanguage, file_symbols, identifier_at, language_for, nodes, parse
from bussola.units.extractors.treesitter import node_text

PYTHON_DOCS = "https://docs.python.org/3/library/{module}.html#{qualified}"
PYPI = "https://pypi.org/project/{name}/"
NODE_DOCS = "https://nodejs.org/api/{module}.html"
NPM = "https://www.npmjs.com/package/{name}"
GO_DOCS = "https://pkg.go.dev/{path}"
PYTHON_ENVIRONMENTS = (".venv", "venv")
SITE_PACKAGES = ("lib/python*/site-packages", "Lib/site-packages")
NODE_MODULES = "node_modules"
NODE_SCHEME = "node:"
NODE_BUILTINS = frozenset(
    {
        *("assert", "async_hooks", "buffer", "child_process", "cluster", "console", "crypto", "dgram", "dns", "events", "fs", "http", "http2"),
        *("https", "inspector", "module", "net", "os", "path", "perf_hooks", "process", "querystring", "readline", "repl", "stream"),
        *("string_decoder", "timers", "tls", "tty", "url", "util", "v8", "vm", "worker_threads", "zlib"),
    }
)
LOCAL_SPECIFIERS = (".", "/", "@/", "~/", "#")
DOCUMENTATION_LABELS = (("documentation", "docs"), ("homepage", "home", "source", "repository"))
GO_MOD = "go.mod"
GO_TEST_SUFFIX = "_test.go"
GO_VERSION_SEGMENT = re.compile(r"v\d+")
GO_REQUIRE = re.compile(rb"^\s*(?:require\s+)?([^\s()]+)\s+(v[^\s]+)", re.MULTILINE)
GO_MODULE = re.compile(rb"^module\s+(\S+)", re.MULTILINE)
MAX_LIBRARY_FILE_BYTES = 2_000_000


@dataclass(frozen=True)
class Imported:
    family: str
    module: str
    name: str = ""

    @property
    def qualified_name(self) -> str:
        return f"{self.module}.{self.name}" if self.name else self.module

    @property
    def first_name(self) -> str | None:
        return self.name.split(".")[0] if self.name else None


@dataclass(frozen=True)
class LibrarySource:
    path: str
    line: int


@dataclass(frozen=True)
class PackageInfo:
    name: str
    version: str | None = None
    url: str | None = None
    source: LibrarySource | None = None


@dataclass(frozen=True)
class Link:
    field: str
    object: str


LINKS: dict[str, dict[str, Link]] = {
    "python": {"attribute": Link("attribute", "object")},
    "ecmascript": {"member_expression": Link("property", "object"), "nested_type_identifier": Link("name", "module")},
    "go": {"selector_expression": Link("field", "operand"), "qualified_type": Link("name", "package")},
}
ROOT_TYPES = frozenset({"identifier", "package_identifier"})


@dataclass(frozen=True)
class ProjectLayout:
    names: dict[str, frozenset[str]]
    root_names: dict[str, frozenset[str]]
    go_modules: tuple[tuple[str, dict[str, str]], ...] = ()

    @classmethod
    def of(cls, paths: list[str], read: Callable[[str], bytes | None]) -> "ProjectLayout":
        names: dict[str, set[str]] = {}
        root_names: dict[str, set[str]] = {}
        for path in paths:
            language = language_for(path)
            if language is None:
                continue
            parts = PurePosixPath(path).with_suffix("").parts
            names.setdefault(language.family, set()).update(parts)
            root_names.setdefault(language.family, set()).add(parts[0])
        go_modules = tuple(module for path in paths if PurePosixPath(path).name == GO_MOD and (module := _go_mod(read(path) or b"")) is not None)
        return cls(
            {family: frozenset(found) for family, found in names.items()}, {family: frozenset(found) for family, found in root_names.items()}, go_modules
        )

    def is_external(self, imported: Imported) -> bool:
        if imported.family == "go":
            return not any(imported.module == path or imported.module.startswith(f"{path}/") for path, _ in self.go_modules)
        if imported.family == "ecmascript" and imported.module.startswith(LOCAL_SPECIFIERS):
            return False
        top = re.split(r"[./]", imported.module.removeprefix(NODE_SCHEME))[0]
        standard = top in sys.stdlib_module_names if imported.family == "python" else top in NODE_BUILTINS
        known = self.root_names if standard else self.names
        return top not in known.get(imported.family, frozenset())

    def go_requirement(self, import_path: str) -> tuple[str, str] | None:
        found = [
            (path, version)
            for _, requires in self.go_modules
            for path, version in requires.items()
            if import_path == path or import_path.startswith(f"{path}/")
        ]
        return max(found, key=lambda item: len(item[0]), default=None)


def imported_symbol(language: SourceLanguage, source: bytes, row: int, column: int) -> Imported | None:
    tree = parse(language, source)
    node = identifier_at(language, tree, row, column)
    if node is None:
        return None
    family = language.family
    in_statement = _import_statement_name(family, node)
    if in_statement is not None:
        return in_statement
    chain = _chain(LINKS[family], node)
    imported = IMPORTS[family](tree.root_node).get(chain[0]) if chain else None
    if chain is None or imported is None:
        return None
    return Imported(family, imported.module, ".".join(part for part in (imported.name, *chain[1:]) if part))


def package_info(imported: Imported, root: Path, origin: str, layout: ProjectLayout) -> PackageInfo:
    if imported.family == "python":
        return _python_package(imported, root)
    if imported.family == "ecmascript":
        return _node_package(imported, root, origin)
    return _go_package(imported, layout)


def is_library_file(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve()
        if not resolved.is_file() or language_for(resolved.name) is None or resolved.stat().st_size > MAX_LIBRARY_FILE_BYTES:
            return False
    except OSError:
        return False
    if any(resolved.is_relative_to(library) for library in _library_roots(root)):
        return True
    project = root.resolve()
    return resolved.is_relative_to(project) and NODE_MODULES in resolved.relative_to(project).parts


def _library_roots(root: Path) -> list[Path]:
    candidates = [root / environment for environment in PYTHON_ENVIRONMENTS]
    candidates += [path for path in (_go_root(), _go_module_cache()) if path is not None]
    return [candidate.resolve() for candidate in candidates if candidate.is_dir()]


def _chain(links: dict[str, Link], node: Node) -> list[str] | None:
    while (parent := node.parent) is not None and (link := links.get(parent.type)) is not None and parent.child_by_field_name(link.field) == node:
        node = parent
    return _dotted(links, node)


def _dotted(links: dict[str, Link], node: Node) -> list[str] | None:
    if node.type in ROOT_TYPES:
        return [node_text(node)]
    link = links.get(node.type)
    owner = node.child_by_field_name(link.object) if link else None
    member = node.child_by_field_name(link.field) if link else None
    head = _dotted(links, owner) if owner is not None else None
    return [*head, node_text(member)] if head is not None and member is not None else None


def _import_statement_name(family: str, node: Node) -> Imported | None:
    parent = node.parent
    if parent is None:
        return None
    if family == "ecmascript" and parent.type == "import_specifier":
        return _ecmascript_specifier(parent)
    if family == "python" and parent.type == "dotted_name":
        return _python_import_name(node, parent)
    return None


def _ecmascript_specifier(specifier: Node) -> Imported | None:
    statement = _ancestor(specifier, "import_statement")
    source = _string(statement.child_by_field_name("source")) if statement else None
    name = specifier.child_by_field_name("name")
    return Imported("ecmascript", source, node_text(name)) if source and name is not None else None


def _python_import_name(node: Node, dotted: Node) -> Imported | None:
    statement = dotted.parent.parent if dotted.parent is not None and dotted.parent.type == "aliased_import" else dotted.parent
    prefix = ".".join(node_text(part) for part in dotted.named_children if part.start_byte <= node.start_byte)
    if statement is not None and statement.type == "import_statement":
        return Imported("python", prefix)
    module = statement.child_by_field_name("module_name") if statement is not None and statement.type == "import_from_statement" else None
    if module is None or module.type != "dotted_name":
        return None
    return Imported("python", prefix) if module == dotted else Imported("python", node_text(module), node_text(dotted))


def _ancestor(node: Node, kind: str) -> Node | None:
    while node.parent is not None:
        node = node.parent
        if node.type == kind:
            return node
    return None


def _string(node: Node | None) -> str | None:
    if node is None or node.type not in ("string", "interpreted_string_literal"):
        return None
    return node_text(node)[1:-1] or None


def _python_imports(root: Node) -> dict[str, Imported]:
    bound: dict[str, Imported] = {}
    for node in nodes(root):
        if node.type == "import_statement":
            for child in node.children_by_field_name("name"):
                alias = child.child_by_field_name("alias")
                dotted = child.child_by_field_name("name") if alias is not None else child
                if alias is not None and dotted is not None:
                    bound[node_text(alias)] = Imported("python", node_text(dotted))
                elif dotted is not None:
                    top = node_text(dotted).split(".")[0]
                    bound[top] = Imported("python", top)
        elif node.type == "import_from_statement":
            module = node.child_by_field_name("module_name")
            if module is None or module.type != "dotted_name":
                continue
            for child in node.children_by_field_name("name"):
                alias = child.child_by_field_name("alias")
                name = child.child_by_field_name("name") if alias is not None else child
                if name is not None:
                    bound[node_text(alias if alias is not None else name)] = Imported("python", node_text(module), node_text(name))
    return bound


def _ecmascript_imports(root: Node) -> dict[str, Imported]:
    bound: dict[str, Imported] = {}
    for node in nodes(root):
        if node.type == "import_statement":
            source = _string(node.child_by_field_name("source"))
            clause = next((child for child in node.named_children if child.type == "import_clause"), None)
            if source and clause is not None:
                bound.update(_import_clause(source, clause))
        elif node.type == "variable_declarator":
            source = _required(node.child_by_field_name("value"))
            target = node.child_by_field_name("name")
            if source is None or target is None:
                continue
            if target.type == "identifier":
                bound[node_text(target)] = Imported("ecmascript", source)
            elif target.type == "object_pattern":
                for item in target.named_children:
                    if item.type == "shorthand_property_identifier_pattern":
                        bound[node_text(item)] = Imported("ecmascript", source, node_text(item))
    return bound


def _import_clause(source: str, clause: Node) -> Iterator[tuple[str, Imported]]:
    for part in clause.named_children:
        if part.type == "identifier":
            yield node_text(part), Imported("ecmascript", source)
        elif part.type == "namespace_import":
            yield from ((node_text(child), Imported("ecmascript", source)) for child in part.named_children if child.type == "identifier")
        elif part.type == "named_imports":
            for specifier in part.named_children:
                name, alias = specifier.child_by_field_name("name"), specifier.child_by_field_name("alias")
                if specifier.type == "import_specifier" and name is not None:
                    yield node_text(alias if alias is not None else name), Imported("ecmascript", source, node_text(name))


def _required(value: Node | None) -> str | None:
    if value is None or value.type != "call_expression":
        return None
    function, arguments = value.child_by_field_name("function"), value.child_by_field_name("arguments")
    if function is None or node_text(function) != "require" or arguments is None or arguments.named_child_count != 1:
        return None
    return _string(arguments.named_children[0])


def _go_imports(root: Node) -> dict[str, Imported]:
    bound: dict[str, Imported] = {}
    for node in nodes(root):
        if node.type != "import_spec":
            continue
        path = _string(node.child_by_field_name("path"))
        alias = node.child_by_field_name("name")
        if path is None or (alias is not None and alias.type != "package_identifier"):
            continue
        bound[node_text(alias) if alias is not None else _go_package_name(path)] = Imported("go", path)
    return bound


def _go_package_name(path: str) -> str:
    segments = path.split("/")
    last = segments[-2] if len(segments) > 1 and GO_VERSION_SEGMENT.fullmatch(segments[-1]) else segments[-1]
    return last.split(".")[0]


IMPORTS: dict[str, Callable[[Node], dict[str, Imported]]] = {"python": _python_imports, "ecmascript": _ecmascript_imports, "go": _go_imports}


def _go_mod(content: bytes) -> tuple[str, dict[str, str]] | None:
    module = GO_MODULE.search(content)
    if module is None:
        return None
    requires = {path.decode(): version.decode() for path, version in GO_REQUIRE.findall(content)}
    return module.group(1).decode(), requires


def _python_package(imported: Imported, root: Path) -> PackageInfo:
    top = imported.module.split(".")[0]
    if top in sys.stdlib_module_names:
        return PackageInfo(top, url=PYTHON_DOCS.format(module=imported.module, qualified=imported.qualified_name))
    for site in _site_packages(root):
        found = _distributions(site, site.stat().st_mtime_ns).get(top)
        source = _python_source(site, imported)
        if found is not None or source is not None:
            name, version, url = found or (top, None, None)
            return PackageInfo(name, version, url or PYPI.format(name=name), source)
    return PackageInfo(top, url=PYPI.format(name=top))


def _site_packages(root: Path) -> list[Path]:
    return [site for environment in PYTHON_ENVIRONMENTS for pattern in SITE_PACKAGES for site in sorted((root / environment).glob(pattern)) if site.is_dir()]


@lru_cache(maxsize=8)
def _distributions(site: Path, _modified: int) -> dict[str, tuple[str, str | None, str | None]]:
    found: dict[str, tuple[str, str | None, str | None]] = {}
    for distribution in distributions(path=[str(site)]):
        name = distribution.metadata["Name"]
        if not name:
            continue
        for top in _top_levels(distribution):
            found.setdefault(top, (name, distribution.version, _project_url(distribution)))
    return found


def _top_levels(distribution: Distribution) -> set[str]:
    listed = (distribution.read_text("top_level.txt") or "").split()
    if listed:
        return set(listed)
    return {PurePosixPath(str(file)).parts[0].removesuffix(".py") for file in distribution.files or [] if not str(file).startswith("..")}


def _project_url(distribution: Distribution) -> str | None:
    labelled: dict[str, str] = {}
    for entry in distribution.metadata.get_all("Project-URL") or []:
        label, _, url = entry.partition(",")
        labelled.setdefault(label.strip().lower(), url.strip())
    for labels in DOCUMENTATION_LABELS:
        url = next((labelled[label] for label in labels if label in labelled), None)
        if url and _is_web(url):
            return url
    home = distribution.metadata["Home-page"]
    return home if home and _is_web(home) else None


def _python_source(site: Path, imported: Imported) -> LibrarySource | None:
    parts = imported.qualified_name.split(".")
    for end in range(len(parts), 0, -1):
        base = site.joinpath(*parts[:end])
        for candidate in (base.with_name(f"{base.name}.py"), base / "__init__.py", base.with_name(f"{base.name}.pyi"), base / "__init__.pyi"):
            if candidate.is_file():
                rest = parts[end : end + 1]
                return LibrarySource(str(candidate), (_defined_at(candidate, rest[0]) if rest else None) or 1)
    return None


def _node_package(imported: Imported, root: Path, origin: str) -> PackageInfo:
    specifier = imported.module.removeprefix(NODE_SCHEME)
    segments = specifier.split("/")
    if imported.module.startswith(NODE_SCHEME) or segments[0] in NODE_BUILTINS:
        return PackageInfo(segments[0], url=NODE_DOCS.format(module=segments[0]))
    count = 2 if specifier.startswith("@") else 1
    if len(segments) < count or any(segment in ("", ".", "..") for segment in segments):
        return PackageInfo(specifier)
    name, subpath = "/".join(segments[:count]), "/".join(segments[count:])
    project = root.resolve()
    directory = (project / origin).parent
    while directory.is_relative_to(project):
        modules = directory / NODE_MODULES
        manifest = _json(modules / name / "package.json")
        if manifest is not None:
            version = manifest.get("version")
            homepage = manifest.get("homepage")
            url = homepage if isinstance(homepage, str) and _is_web(homepage) else NPM.format(name=name)
            return PackageInfo(name, version if isinstance(version, str) else None, url, _node_source(modules, name, subpath, manifest, imported.first_name))
        if directory == project:
            break
        directory = directory.parent
    return PackageInfo(name, url=NPM.format(name=name))


def _node_source(modules: Path, name: str, subpath: str, manifest: dict[str, Any], symbol: str | None) -> LibrarySource | None:
    package = modules / name
    typings = modules / "@types" / name.removeprefix("@").replace("/", "__")
    if subpath:
        entries = [
            package / f"{subpath}.d.ts",
            package / subpath / "index.d.ts",
            package / f"{subpath}.js",
            package / subpath / "index.js",
            typings / f"{subpath}.d.ts",
        ]
    else:
        declared = [manifest.get(key) for key in ("types", "typings", "main")]
        named = [package / entry for entry in declared if isinstance(entry, str) and entry]
        entries = [*named, *(path.with_name(f"{path.name}.js") for path in named), package / "index.d.ts", package / "index.js", typings / "index.d.ts"]
    existing = [entry for entry in entries if entry.is_file() and language_for(entry.name) is not None]
    for entry in existing:
        line = _defined_at(entry, symbol) if symbol else None
        if line is not None:
            return LibrarySource(str(entry), line)
    return LibrarySource(str(existing[0]), 1) if existing else None


def _go_package(imported: Imported, layout: ProjectLayout) -> PackageInfo:
    url = GO_DOCS.format(path=imported.module) + (f"#{imported.name}" if imported.name else "")
    if "." not in imported.module.split("/")[0]:
        go_root = _go_root()
        return PackageInfo(imported.module, url=url, source=_go_source(go_root / "src" / imported.module, imported.first_name) if go_root else None)
    requirement = layout.go_requirement(imported.module)
    if requirement is None:
        return PackageInfo(imported.module, url=url)
    module, version = requirement
    cache = _go_module_cache()
    directory = cache / f"{_go_escape(module)}@{_go_escape(version)}" / imported.module.removeprefix(module).lstrip("/") if cache else None
    return PackageInfo(module, version, url, _go_source(directory, imported.first_name) if directory else None)


def _go_source(directory: Path, symbol: str | None) -> LibrarySource | None:
    if symbol is None or not directory.is_dir():
        return None
    for path in sorted(directory.glob("*.go")):
        line = None if path.name.endswith(GO_TEST_SUFFIX) else _defined_at(path, symbol)
        if line is not None:
            return LibrarySource(str(path), line)
    return None


def _go_root() -> Path | None:
    configured = os.environ.get("GOROOT")
    if configured:
        return Path(configured)
    go = shutil.which("go")
    return Path(go).resolve().parents[1] if go else None


def _go_module_cache() -> Path | None:
    configured = os.environ.get("GOMODCACHE")
    if configured:
        return Path(configured)
    go_path = os.environ.get("GOPATH", "").split(os.pathsep)[0]
    return Path(go_path) / "pkg" / "mod" if go_path else Path.home() / "go" / "pkg" / "mod"


def _go_escape(path: str) -> str:
    return re.sub(r"[A-Z]", lambda match: f"!{match.group(0).lower()}", path)


def _defined_at(path: Path, name: str) -> int | None:
    language = language_for(path.name)
    try:
        if language is None or path.stat().st_size > MAX_LIBRARY_FILE_BYTES:
            return None
        source = path.read_bytes()
    except OSError:
        return None
    return next((symbol.row + 1 for symbol in file_symbols(language, source).definitions if symbol.name == name), None)


def _json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return cast(dict[str, Any], value) if isinstance(value, dict) else None


def _is_web(url: str) -> bool:
    return url.startswith(("https://", "http://"))
