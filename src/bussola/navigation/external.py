import json
import os
import posixpath
import re
import shutil
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import Distribution, distributions
from pathlib import Path, PurePosixPath
from typing import Any, cast

from tree_sitter import Node, Tree

from bussola.navigation.definitions import Definition, find_definition, python_module_file
from bussola.navigation.docs_links import GO_DOCS, NODE_DOCS, NODE_SCHEME, node_builtin, symbol_docs_url
from bussola.navigation.symbols import SourceLanguage, language_for, nodes
from bussola.units.extractors.treesitter import node_text
from bussola.units.modules import GO_MOD, go_module_name

PYPI = "https://pypi.org/project/{name}/"
NPM = "https://www.npmjs.com/package/{name}"
PYTHON_ENVIRONMENTS = (".venv", "venv")
SITE_PACKAGES = ("lib/python*/site-packages", "Lib/site-packages")
NODE_MODULES = "node_modules"
LOCAL_SPECIFIERS = (".", "/", "@/", "~/", "#")
DOCUMENTATION_LABELS = (("documentation", "docs"), ("homepage", "home", "source", "repository"))
GO_TEST_SUFFIX = "_test.go"
GO_VERSION_SEGMENT = re.compile(r"v\d+")
PACKAGE_JSON = "package.json"
SCRIPT_CONFIG = re.compile(r"(?:tsconfig.*|jsconfig)\.json")
WILDCARD = "*"
JSON_STRING_OR_COMMENT = re.compile(r'("(?:\\.|[^"\\])*")|//[^\n]*|/\*.*?\*/', re.DOTALL)
JSON_TRAILING_COMMA = re.compile(r",(\s*[}\]])")


@dataclass(frozen=True)
class Imported:
    family: str
    module: str
    name: str = ""

    @property
    def qualified_name(self) -> str:
        return f"{self.module}.{self.name}" if self.name else self.module

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self.name.split(".")) if self.name else ()

    @property
    def docs_url(self) -> str | None:
        return symbol_docs_url(self.family, self.module, self.name, None, None)


@dataclass(frozen=True)
class LibrarySource:
    path: str
    line: int


@dataclass(frozen=True)
class PackageInfo:
    name: str
    version: str | None = None
    url: str | None = None
    home_url: str | None = None
    definition: Definition | None = None


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
    python_modules: frozenset[str] = frozenset()
    python_roots: frozenset[str] = frozenset()
    script_modules: frozenset[str] = frozenset()
    script_bases: tuple[str, ...] = ()
    script_aliases: tuple[str, ...] = ()
    go_modules: tuple[tuple[str, dict[str, str]], ...] = ()

    @classmethod
    def of(cls, paths: list[str], read: Callable[[str], bytes | None]) -> "ProjectLayout":
        families = {path: language.family for path in paths if (language := language_for(path)) is not None}
        python = [PurePosixPath(path) for path, family in families.items() if family == "python"]
        scripts = [PurePosixPath(path) for path, family in families.items() if family == "ecmascript"]
        configs = [_script_config(PurePosixPath(path), _jsonc(read(path) or b"")) for path in paths if SCRIPT_CONFIG.fullmatch(PurePosixPath(path).name)]
        workspaces = [name for path in paths if PurePosixPath(path).name == PACKAGE_JSON and isinstance(name := _jsonc(read(path) or b"").get("name"), str)]
        go_modules = tuple(module for path in paths if PurePosixPath(path).name == GO_MOD and (module := _go_mod(read(path) or b"")) is not None)
        return cls(
            python_modules=_python_modules(python),
            python_roots=frozenset(path.with_suffix("").parts[0] for path in python),
            script_modules=frozenset(str(module) for path in scripts for module in (path.with_suffix(""), *path.parents)),
            script_bases=tuple(base for base, _ in configs if base is not None),
            script_aliases=tuple(alias for _, aliases in configs for alias in aliases) + tuple(alias for name in workspaces for alias in (name, f"{name}/*")),
            go_modules=go_modules,
        )

    def is_external(self, imported: Imported) -> bool:
        if imported.family == "go":
            return not any(imported.module == path or imported.module.startswith(f"{path}/") for path, _ in self.go_modules)
        if imported.family == "python":
            top = imported.module.split(".")[0]
            return top not in (self.python_roots if top in sys.stdlib_module_names else self.python_modules)
        specifier = imported.module
        if specifier.startswith(LOCAL_SPECIFIERS) or any(_alias_matches(alias, specifier) for alias in self.script_aliases):
            return False
        return specifier.startswith(NODE_SCHEME) or not any(
            posixpath.normpath(posixpath.join(base, specifier)) in self.script_modules for base in self.script_bases
        )

    def go_requirement(self, import_path: str) -> tuple[str, str] | None:
        found = [
            (path, version)
            for _, requires in self.go_modules
            for path, version in requires.items()
            if import_path == path or import_path.startswith(f"{path}/")
        ]
        return max(found, key=lambda item: len(item[0]), default=None)


def imported_symbol(language: SourceLanguage, tree: Tree, node: Node) -> Imported | None:
    family = language.family
    in_statement = _import_statement_name(family, node)
    if in_statement is not None:
        return in_statement
    chain = _chain(LINKS[family], node)
    imported = IMPORTS[family](tree.root_node).get(chain[0]) if chain else None
    if chain is None or imported is None:
        return None
    return Imported(family, imported.module, ".".join(part for part in (imported.name, *chain[1:]) if part))


def package_info(imported: Imported, root: Path, origin_dir: str, layout: ProjectLayout) -> PackageInfo:
    if imported.family == "python":
        return _python_package(imported, root)
    if imported.family == "ecmascript":
        return _node_package(imported, root, origin_dir)
    return _go_package(imported, layout)


def is_library_file(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve()
        if not resolved.is_file() or language_for(resolved.name) is None:
            return False
    except OSError:
        return False
    if any(resolved.is_relative_to(library) for library in _library_roots(root)):
        return True
    project = root.resolve()
    return resolved.is_relative_to(project) and NODE_MODULES in resolved.relative_to(project).parts


def _library_roots(root: Path) -> list[Path]:
    project = root.resolve()
    environments = [resolved for environment in PYTHON_ENVIRONMENTS if (resolved := (root / environment).resolve()).is_relative_to(project)]
    go = [path.resolve() for path in (_go_root(), _go_module_cache()) if path is not None]
    return [candidate for candidate in environments + go if candidate.is_dir()]


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
    return last.split(".")[0].removeprefix("go-").removesuffix("-go").replace("-", "")


IMPORTS: dict[str, Callable[[Node], dict[str, Imported]]] = {"python": _python_imports, "ecmascript": _ecmascript_imports, "go": _go_imports}


def _go_mod(content: bytes) -> tuple[str, dict[str, str]] | None:
    module = go_module_name(content)
    return (module, _go_requires(content)) if module is not None else None


def _go_requires(content: bytes) -> dict[str, str]:
    requires: dict[str, str] = {}
    in_block = False
    for line in content.decode(errors="replace").splitlines():
        words = line.split("//", 1)[0].split()
        if words[:1] == ["require"]:
            in_block, entry = words[1:] == ["("], words[1:]
        elif words[:1] == [")"]:
            in_block, entry = False, []
        else:
            entry = words if in_block else []
        match entry:
            case [path, version, *_] if path != "(":
                requires[path] = version
            case _:
                pass
    return requires


def _python_modules(paths: list[PurePosixPath]) -> frozenset[str]:
    packages = {path.parent for path in paths if path.stem == "__init__" and path.parent != PurePosixPath(".")}
    return frozenset(part for path in paths for index, part in enumerate(path.with_suffix("").parts) if PurePosixPath(*path.parts[:index]) not in packages)


def _script_config(path: PurePosixPath, config: dict[str, Any]) -> tuple[str | None, list[str]]:
    options = config.get("compilerOptions")
    options = cast(dict[str, Any], options) if isinstance(options, dict) else {}
    base, paths = options.get("baseUrl"), options.get("paths")
    aliases = [key for key in cast(dict[str, Any], paths) if key != WILDCARD] if isinstance(paths, dict) else []
    return (posixpath.normpath(posixpath.join(str(path.parent), base)) if isinstance(base, str) else None), aliases


def _alias_matches(alias: str, specifier: str) -> bool:
    return specifier.startswith(alias.removesuffix(WILDCARD)) if alias.endswith(WILDCARD) else specifier == alias


def _jsonc(content: bytes) -> dict[str, Any]:
    text = JSON_STRING_OR_COMMENT.sub(lambda match: match.group(1) or "", content.decode(errors="replace"))
    try:
        value = json.loads(JSON_TRAILING_COMMA.sub(r"\1", text))
    except ValueError:
        return {}
    return cast(dict[str, Any], value) if isinstance(value, dict) else {}


def _python_package(imported: Imported, root: Path) -> PackageInfo:
    top = imported.module.split(".")[0]
    if top in sys.stdlib_module_names:
        return PackageInfo(top, url=imported.docs_url)
    for site in _site_packages(root):
        found = _distributions(site, site.stat().st_mtime_ns).get(top)
        definition = _python_definition(site, imported)
        if found is not None or definition is not None:
            name, version, docs = found or (top, None, None)
            url = symbol_docs_url(imported.family, imported.module, imported.name, version, docs)
            return PackageInfo(name, version, url, docs or PYPI.format(name=name), definition)
    return PackageInfo(top, url=imported.docs_url, home_url=PYPI.format(name=top))


def python_server_settings(root: Path) -> dict[str, Any]:
    paths = [str(site) for site in _site_packages(root)]
    analysis = {"extraPaths": paths}
    return {"python": {"analysis": analysis}, "python.analysis": analysis, "basedpyright.analysis": analysis} if paths else {}


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


def _python_definition(site: Path, imported: Imported) -> Definition | None:
    parts = imported.qualified_name.split(".")
    for end in range(len(parts), 0, -1):
        module = python_module_file(site.joinpath(*parts[:end]))
        if module is not None:
            return find_definition(module, tuple(parts[end:]), site) or Definition(module, 1)
    return None


def _node_package(imported: Imported, root: Path, origin_dir: str) -> PackageInfo:
    builtin = node_builtin(imported.module)
    if builtin is not None:
        return PackageInfo(builtin, url=imported.docs_url, home_url=NODE_DOCS.format(module=builtin))
    specifier = imported.module
    segments = specifier.split("/")
    count = 2 if specifier.startswith("@") else 1
    if len(segments) < count or any(segment in ("", ".", "..") for segment in segments):
        return PackageInfo(specifier, url=imported.docs_url)
    name, subpath = "/".join(segments[:count]), "/".join(segments[count:])
    project = root.resolve()
    directory = project / origin_dir
    while directory.is_relative_to(project):
        modules = directory / NODE_MODULES
        manifest = _json(modules / name / "package.json")
        if manifest is not None:
            version = manifest.get("version")
            homepage = manifest.get("homepage")
            home = homepage if isinstance(homepage, str) and _is_web(homepage) else NPM.format(name=name)
            definition = _node_definition(modules, name, subpath, manifest, imported.names)
            return PackageInfo(name, version if isinstance(version, str) else None, imported.docs_url, home, definition)
        if directory == project:
            break
        directory = directory.parent
    return PackageInfo(name, url=imported.docs_url, home_url=NPM.format(name=name))


def _node_definition(modules: Path, name: str, subpath: str, manifest: dict[str, Any], names: tuple[str, ...]) -> Definition | None:
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
    found = next((definition for entry in existing if names and (definition := find_definition(entry, names)) is not None), None)
    return found or (Definition(existing[0], 1) if existing else None)


def _go_package(imported: Imported, layout: ProjectLayout) -> PackageInfo:
    home = GO_DOCS.format(path=imported.module) if imported.name else None
    if "." not in imported.module.split("/")[0]:
        go_root = _go_root()
        definition = _go_definition(go_root / "src" / imported.module, imported.names) if go_root else None
        return PackageInfo(imported.module, url=imported.docs_url, home_url=home, definition=definition)
    requirement = layout.go_requirement(imported.module)
    if requirement is None:
        return PackageInfo(imported.module, url=imported.docs_url, home_url=home)
    module, version = requirement
    cache = _go_module_cache()
    directory = cache / f"{_go_escape(module)}@{_go_escape(version)}" / imported.module.removeprefix(module).lstrip("/") if cache else None
    return PackageInfo(module, version, imported.docs_url, home, _go_definition(directory, imported.names) if directory else None)


def _go_definition(directory: Path, names: tuple[str, ...]) -> Definition | None:
    if not names or not directory.is_dir():
        return None
    files = (path for path in sorted(directory.glob("*.go")) if not path.name.endswith(GO_TEST_SUFFIX))
    return next((definition for path in files if (definition := find_definition(path, names)) is not None), None)


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


def _json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return cast(dict[str, Any], value) if isinstance(value, dict) else None


def _is_web(url: str) -> bool:
    return url.startswith(("https://", "http://"))
