from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import PurePosixPath

import tree_sitter_go
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser, Tree


@dataclass(frozen=True)
class Symbol:
    name: str
    row: int
    start: int
    end: int
    definition: bool


@dataclass(frozen=True)
class SourceLanguage:
    family: str
    grammar: Language
    identifiers: frozenset[str]
    is_definition: Callable[[Node], bool]


@dataclass(frozen=True)
class FileSymbols:
    definitions: tuple[Symbol, ...]
    used_names: tuple[str, ...]


PYTHON_DEFINITIONS = frozenset({"function_definition", "class_definition"})
ECMASCRIPT_DEFINITIONS = frozenset(
    {
        "function_declaration",
        "generator_function_declaration",
        "function_signature",
        "class_declaration",
        "abstract_class_declaration",
        "method_definition",
        "method_signature",
        "abstract_method_signature",
        "interface_declaration",
        "type_alias_declaration",
        "enum_declaration",
    }
)
GO_DEFINITIONS = frozenset({"function_declaration", "method_declaration", "type_spec", "type_alias"})
GO_VARIABLES = frozenset({"var_spec", "const_spec"})
ECMASCRIPT_IDENTIFIERS = frozenset(
    {"identifier", "property_identifier", "type_identifier", "shorthand_property_identifier", "shorthand_property_identifier_pattern"}
)


def _is_name_of(node: Node, parent_types: frozenset[str]) -> bool:
    parent = node.parent
    return parent is not None and parent.type in parent_types and parent.child_by_field_name("name") == node


def _python_definition(node: Node) -> bool:
    return _is_name_of(node, PYTHON_DEFINITIONS) or _is_module_assignment_target(node)


def _is_module_assignment_target(node: Node) -> bool:
    assignment = node.parent
    if assignment is None or assignment.type != "assignment" or assignment.child_by_field_name("left") != node:
        return False
    while assignment.parent is not None and assignment.parent.type == "assignment":
        assignment = assignment.parent
    statement = assignment.parent
    return statement is not None and statement.type == "expression_statement" and _parent_type(statement) == "module"


def _ecmascript_definition(node: Node) -> bool:
    if _is_name_of(node, ECMASCRIPT_DEFINITIONS):
        return True
    declarator = node.parent
    if declarator is None or declarator.type != "variable_declarator" or declarator.child_by_field_name("name") != node:
        return False
    scope = declarator.parent.parent if declarator.parent else None
    if scope is not None and scope.type == "export_statement":
        scope = scope.parent
    return scope is not None and scope.type == "program"


def _go_definition(node: Node) -> bool:
    if _is_name_of(node, GO_DEFINITIONS):
        return True
    spec = node.parent
    if spec is None or spec.type not in GO_VARIABLES or node not in spec.children_by_field_name("name"):
        return False
    declaration = spec.parent
    if declaration is not None and declaration.type == "var_spec_list":
        declaration = declaration.parent
    return declaration is not None and _parent_type(declaration) == "source_file"


def _parent_type(node: Node) -> str | None:
    return node.parent.type if node.parent else None


PYTHON = SourceLanguage("python", Language(tree_sitter_python.language()), frozenset({"identifier"}), _python_definition)
TYPESCRIPT = SourceLanguage("ecmascript", Language(tree_sitter_typescript.language_typescript()), ECMASCRIPT_IDENTIFIERS, _ecmascript_definition)
TSX = SourceLanguage("ecmascript", Language(tree_sitter_typescript.language_tsx()), ECMASCRIPT_IDENTIFIERS, _ecmascript_definition)
JAVASCRIPT = SourceLanguage("ecmascript", Language(tree_sitter_javascript.language()), ECMASCRIPT_IDENTIFIERS, _ecmascript_definition)
GO = SourceLanguage("go", Language(tree_sitter_go.language()), frozenset({"identifier", "field_identifier", "type_identifier"}), _go_definition)

LANGUAGES_BY_SUFFIX: dict[str, SourceLanguage] = {
    ".py": PYTHON,
    ".pyi": PYTHON,
    ".ts": TYPESCRIPT,
    ".tsx": TSX,
    ".js": JAVASCRIPT,
    ".jsx": JAVASCRIPT,
    ".mjs": JAVASCRIPT,
    ".cjs": JAVASCRIPT,
    ".go": GO,
}


def language_for(path: str) -> SourceLanguage | None:
    return LANGUAGES_BY_SUFFIX.get(PurePosixPath(path).suffix.lower())


def file_symbols(language: SourceLanguage, source: bytes) -> FileSymbols:
    definitions: list[Symbol] = []
    used: set[str] = set()
    for symbol in _symbols(language, _parse(language, source)):
        if symbol.definition:
            definitions.append(symbol)
        else:
            used.add(symbol.name)
    return FileSymbols(tuple(definitions), tuple(sorted(used)))


def references(language: SourceLanguage, source: bytes, name: str) -> list[Symbol]:
    return [symbol for symbol in _symbols(language, _parse(language, source)) if symbol.name == name and not symbol.definition]


def symbol_at(language: SourceLanguage, source: bytes, row: int, column: int) -> Symbol | None:
    root = _parse(language, source).root_node
    for candidate in (column, column - 1):
        if candidate < 0:
            continue
        node = root.descendant_for_point_range((row, candidate), (row, candidate))
        if node is not None and node.type in language.identifiers and node.start_point[0] == row:
            return _symbol(language, node)
    return None


def _parse(language: SourceLanguage, source: bytes) -> Tree:
    return Parser(language.grammar).parse(source)


def _symbols(language: SourceLanguage, tree: Tree) -> Iterator[Symbol]:
    for node in _nodes(tree):
        if node.type in language.identifiers and node.start_point[0] == node.end_point[0]:
            yield _symbol(language, node)


def _symbol(language: SourceLanguage, node: Node) -> Symbol:
    (row, start), (_, end) = node.start_point, node.end_point
    name = node.text.decode(errors="replace") if node.text else ""
    return Symbol(name, row, start, end, language.is_definition(node))


def _nodes(tree: Tree) -> Iterator[Node]:
    cursor = tree.walk()
    while True:
        if cursor.node is not None:
            yield cursor.node
        if cursor.goto_first_child():
            continue
        while not cursor.goto_next_sibling():
            if not cursor.goto_parent():
                return
