import inspect
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from tree_sitter import Node, Tree

from bussola.navigation.index import MAX_FILE_BYTES
from bussola.navigation.symbols import SourceLanguage, language_for, nodes, parse
from bussola.units.extractors.treesitter import node_text

MAX_REEXPORT_DEPTH = 4
MAX_SIGNATURE_LINES = 12
HOVER_FENCE = re.compile(r"\A\s*```(\w*)\n(.*?)\n?```\s*(.*)\Z", re.DOTALL)
HOVER_RULE = "---"
STRING_PREFIX = re.compile(r"\A[rRbBuUfF]*")
STRING_QUOTES = ('"""', "'''", '"', "'")
JSDOC_START = "/**"
GO_COMMENT = "//"
SIGNATURE_ENDINGS = (":", "{", ";", "=")
STATEMENT_WRAPPERS = frozenset(
    {"export_statement", "ambient_declaration", "lexical_declaration", "variable_declaration", "type_declaration", "var_declaration", "const_declaration"}
)
DECLARATION_KEYWORDS = {"type_spec": "type ", "type_alias": "type ", "var_spec": "var ", "const_spec": "const "}
SCRIPT_EXTENSIONS = (".d.ts", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".jsx")
SCRIPT_INDEXES = ("index.d.ts", "index.ts", "index.js")
PYTHON_EXTENSIONS = (".py", ".pyi")
PYTHON_PACKAGE = "__init__"
MODULE_BLOCKS = frozenset({"if_statement", "else_clause", "elif_clause", "try_statement", "except_clause", "block"})
CODE_LANGUAGES = {"python": "python", "ecmascript": "typescript", "go": "go"}


@dataclass(frozen=True)
class Definition:
    path: Path
    line: int
    signature: str | None = None
    docstring: str | None = None


@dataclass(frozen=True)
class HoverDoc:
    signature: str | None
    language: str | None
    docstring: str | None


def from_hover(text: str) -> HoverDoc:
    match = HOVER_FENCE.match(text)
    if match is None:
        return HoverDoc(None, None, text.strip() or None)
    rest = match.group(3).strip().removeprefix(HOVER_RULE).strip()
    return HoverDoc(match.group(2).strip() or None, match.group(1) or None, rest or None)


def find_definition(path: Path, names: tuple[str, ...], package_root: Path | None = None) -> Definition | None:
    return _find(path, names, package_root, 0)


def python_module_file(base: Path) -> Path | None:
    candidates = [base.with_name(f"{base.name}{suffix}") for suffix in PYTHON_EXTENSIONS] + [base / f"{PYTHON_PACKAGE}{suffix}" for suffix in PYTHON_EXTENSIONS]
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _find(path: Path, names: tuple[str, ...], package_root: Path | None, depth: int) -> Definition | None:
    parsed = _parsed(path)
    if parsed is None:
        return None
    language, tree = parsed
    if not names:
        return Definition(path, 1, None, _module_docstring(language, tree))
    node = _definition(language, tree.root_node, names)
    if node is not None:
        return Definition(path, node.start_point[0] + 1, _signature(node), _docstring(language, node))
    if depth >= MAX_REEXPORT_DEPTH:
        return None
    for target, name in _reexports(language, tree, path, names[0], package_root):
        found = _find(target, (name, *names[1:]), package_root, depth + 1)
        if found is not None:
            return found
    return None


def _parsed(path: Path) -> tuple[SourceLanguage, Tree] | None:
    language = language_for(path.name)
    try:
        status = path.stat()
    except OSError:
        return None
    if language is None or status.st_size > MAX_FILE_BYTES:
        return None
    tree = _parse_file(path, status.st_mtime_ns, status.st_size)
    return (language, tree) if tree is not None else None


@lru_cache(maxsize=32)
def _parse_file(path: Path, _modified: int, _size: int) -> Tree | None:
    language = language_for(path.name)
    try:
        return parse(language, path.read_bytes()) if language is not None else None
    except OSError:
        return None


def _definition(language: SourceLanguage, scope: Node, names: tuple[str, ...]) -> Node | None:
    found: Node | None = None
    for name in names:
        found = _shallowest(language, scope, name)
        if found is None:
            return None
        scope = found
    return found


def _shallowest(language: SourceLanguage, scope: Node, name: str) -> Node | None:
    wanted = name.encode()
    matches = [node for node in nodes(scope) if node.type in language.identifiers and node.text == wanted and language.is_definition(node)]
    declarations = [declaration for node in matches if (declaration := node.parent) is not None and declaration != scope]
    return min(declarations, key=_depth, default=None)


def _depth(node: Node) -> int:
    depth = 0
    while node.parent is not None:
        node, depth = node.parent, depth + 1
    return depth


def _signature(declaration: Node) -> str | None:
    body = _body(declaration)
    start = declaration.parent if declaration.type == "variable_declarator" and declaration.parent is not None else declaration
    end = body.start_byte if body is not None else declaration.end_byte
    text = (start.text or b"")[: end - start.start_byte].decode(errors="replace")
    text = (text.split("{")[0] if declaration.type in DECLARATION_KEYWORDS else text).rstrip()
    while text.endswith(SIGNATURE_ENDINGS):
        text = text[:-1].rstrip()
    lines = inspect.cleandoc(text).splitlines()
    signature = "\n".join(lines[:MAX_SIGNATURE_LINES]) + ("\n..." if len(lines) > MAX_SIGNATURE_LINES else "")
    return f"{DECLARATION_KEYWORDS.get(declaration.type, '')}{signature}" or None


def _body(declaration: Node) -> Node | None:
    body = declaration.child_by_field_name("body")
    if body is not None:
        return body
    value = declaration.child_by_field_name("value") if declaration.type == "variable_declarator" else None
    return (value.child_by_field_name("body") or value) if value is not None else None


def _docstring(language: SourceLanguage, declaration: Node) -> str | None:
    if language.family == "python":
        return _python_docstring(declaration.child_by_field_name("body"))
    statement = declaration
    while statement.parent is not None and statement.parent.type in STATEMENT_WRAPPERS:
        statement = statement.parent
    return _jsdoc(statement) if language.family == "ecmascript" else _go_doc(statement)


def _module_docstring(language: SourceLanguage, tree: Tree) -> str | None:
    return _python_docstring(tree.root_node) if language.family == "python" else None


def _python_docstring(body: Node | None) -> str | None:
    first = body.named_children[0] if body is not None and body.named_children else None
    string = first.named_children[0] if first is not None and first.type == "expression_statement" and first.named_children else None
    if string is None or string.type != "string":
        return None
    text = STRING_PREFIX.sub("", node_text(string))
    quote = next((quote for quote in STRING_QUOTES if text.startswith(quote) and text.endswith(quote) and len(text) >= 2 * len(quote)), None)
    return inspect.cleandoc(text[len(quote) : -len(quote)]) or None if quote else None


def _jsdoc(statement: Node) -> str | None:
    comment = statement.prev_named_sibling
    if comment is None or comment.type != "comment" or comment.end_point[0] < statement.start_point[0] - 1:
        return None
    text = node_text(comment)
    if not text.startswith(JSDOC_START):
        return None
    lines = [line.strip().removeprefix("*").removeprefix(" ") for line in text.removeprefix(JSDOC_START).removesuffix("*/").splitlines()]
    return inspect.cleandoc("\n".join(lines)) or None


def _go_doc(statement: Node) -> str | None:
    lines: list[str] = []
    comment, row = statement.prev_named_sibling, statement.start_point[0]
    while comment is not None and comment.type == "comment" and comment.end_point[0] == row - 1:
        text = node_text(comment)
        lines[:0] = (
            [text.removeprefix(GO_COMMENT).removeprefix(" ")] if text.startswith(GO_COMMENT) else text.removeprefix("/*").removesuffix("*/").splitlines()
        )
        comment, row = comment.prev_named_sibling, comment.start_point[0]
    return inspect.cleandoc("\n".join(lines)) or None


def _reexports(language: SourceLanguage, tree: Tree, path: Path, name: str, package_root: Path | None) -> list[tuple[Path, str]]:
    if language.family == "python":
        return _python_reexports(tree, path, name, package_root)
    if language.family == "ecmascript":
        return _script_reexports(tree, path, name)
    return []


def _python_reexports(tree: Tree, path: Path, name: str, package_root: Path | None) -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for statement in _module_level(tree.root_node, "import_from_statement"):
        imported = _python_imported_name(statement, name)
        module = statement.child_by_field_name("module_name")
        target = _python_module_path(module, path, package_root) if imported is not None and module is not None else None
        if target is not None and imported is not None:
            found.append((target, imported))
    return found


def _module_level(root: Node, kind: str) -> list[Node]:
    found: list[Node] = []
    for child in root.named_children:
        if child.type == kind:
            found.append(child)
        elif child.type in MODULE_BLOCKS:
            found.extend(_module_level(child, kind))
    return found


def _python_imported_name(statement: Node, name: str) -> str | None:
    if any(child.type == "wildcard_import" for child in statement.named_children):
        return name
    for child in statement.children_by_field_name("name"):
        alias = child.child_by_field_name("alias")
        original = child.child_by_field_name("name") if alias is not None else child
        if original is not None and node_text(alias if alias is not None else original) == name:
            return node_text(original)
    return None


def _python_module_path(module: Node, path: Path, package_root: Path | None) -> Path | None:
    if module.type == "relative_import":
        prefix = next((child for child in module.named_children if child.type == "import_prefix"), None)
        dotted = next((child for child in module.named_children if child.type == "dotted_name"), None)
        base = path.parent
        for _ in range(len(node_text(prefix)) - 1 if prefix is not None else 0):
            base = base.parent
        parts = node_text(dotted).split(".") if dotted is not None else []
    elif package_root is not None:
        base, parts = package_root, node_text(module).split(".")
    else:
        return None
    return python_module_file(base.joinpath(*parts)) if parts else python_module_file(base)


def _script_reexports(tree: Tree, path: Path, name: str) -> list[tuple[Path, str]]:
    found: list[tuple[Path, str]] = []
    for statement in tree.root_node.named_children:
        source = statement.child_by_field_name("source") if statement.type == "export_statement" else None
        specifier = node_text(source)[1:-1] if source is not None else ""
        exported = _script_exported_name(statement, name) if specifier.startswith(".") else None
        target = _script_file(path.parent / specifier) if exported is not None else None
        if target is not None and exported is not None:
            found.append((target, exported))
    return found


def _script_exported_name(statement: Node, name: str) -> str | None:
    clause = next((child for child in statement.named_children if child.type == "export_clause"), None)
    if clause is None:
        return name if not any(child.type == "namespace_export" for child in statement.named_children) else None
    for specifier in clause.named_children:
        original, alias = specifier.child_by_field_name("name"), specifier.child_by_field_name("alias")
        if original is not None and node_text(alias if alias is not None else original) == name:
            return node_text(original)
    return None


def _script_file(base: Path) -> Path | None:
    stem = base.with_name(base.name.removesuffix(".js")) if base.name.endswith(".js") else base
    candidates = [*(stem.with_name(f"{stem.name}{extension}") for extension in SCRIPT_EXTENSIONS), base, *(base / index for index in SCRIPT_INDEXES)]
    return next((candidate for candidate in candidates if candidate.is_file() and language_for(candidate.name) is not None), None)
