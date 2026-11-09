import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from tree_sitter import Language, Node, Parser, Tree

from bussola.units.extractors import ecmascript, go, python
from bussola.units.extractors.javascript import JAVASCRIPT as JAVASCRIPT_EXTRACTOR
from bussola.units.extractors.treesitter import node_text
from bussola.units.extractors.typescript import TSX as TSX_EXTRACTOR
from bussola.units.extractors.typescript import TYPESCRIPT as TYPESCRIPT_EXTRACTOR
from bussola.units.registry import extractor_for


@dataclass(frozen=True)
class Symbol:
    name: str
    row: int
    start: int
    definition: bool
    member: bool = False


@dataclass(frozen=True)
class SourceLanguage:
    family: str
    grammar: Language
    identifiers: frozenset[str]
    is_definition: Callable[[Node], bool]
    is_member_definition: Callable[[Node], bool]
    imports: Callable[[Node], Iterator[str]]


@dataclass(frozen=True)
class FileSymbols:
    definitions: tuple[Symbol, ...]
    used_names: tuple[str, ...]


PYTHON_DEFINITIONS = frozenset({python.FUNCTION_DEFINITION, python.CLASS_DEFINITION})
ECMASCRIPT_MEMBERS = frozenset({ecmascript.METHOD_DEFINITION, "method_signature", "abstract_method_signature"})
ECMASCRIPT_DEFINITIONS = ecmascript.FUNCTION_DECLARATIONS | ecmascript.CLASS_DECLARATIONS | ecmascript.TYPE_DECLARATIONS | ECMASCRIPT_MEMBERS
GO_MEMBERS = frozenset({go.METHOD_DECLARATION})
GO_DEFINITIONS = frozenset({go.FUNCTION_DECLARATION}) | GO_MEMBERS | go.TYPE_SPECS
GO_VARIABLES = frozenset({"var_spec", "const_spec"})
GO_MAJOR_VERSION = re.compile(r"v\d+")
MEMBER_IDENTIFIERS = frozenset({"property_identifier", "field_identifier"})
RECEIVERS = {"attribute": "object", "member_expression": "object", "selector_expression": "operand"}
ECMASCRIPT_IDENTIFIERS = frozenset(
    {"identifier", "property_identifier", "type_identifier", "shorthand_property_identifier", "shorthand_property_identifier_pattern"}
)


def _is_name_of(node: Node, parent_types: frozenset[str]) -> bool:
    parent = node.parent
    return parent is not None and parent.type in parent_types and parent.child_by_field_name("name") == node


def _python_definition(node: Node) -> bool:
    return _is_name_of(node, PYTHON_DEFINITIONS) or _is_declared_assignment_target(node)


def _is_declared_assignment_target(node: Node) -> bool:
    assignment = node.parent
    if assignment is None or assignment.type != "assignment" or assignment.child_by_field_name("left") != node:
        return False
    while assignment.parent is not None and assignment.parent.type == "assignment":
        assignment = assignment.parent
    statement = assignment.parent
    if statement is None or statement.type != "expression_statement" or statement.parent is None:
        return False
    return statement.parent.type == "module" or (statement.parent.type == "block" and _parent_type(statement.parent) == python.CLASS_DEFINITION)


def _python_member(node: Node) -> bool:
    scope = node.parent
    while scope is not None and scope.type not in {"block", "module"}:
        scope = scope.parent
    return scope is not None and scope.type == "block" and _parent_type(scope) == python.CLASS_DEFINITION


def _python_imports(root: Node) -> Iterator[str]:
    for node in nodes(root):
        if node.type in {"import_statement", "import_from_statement"}:
            for name in node.children_by_field_name("name"):
                bound = name.child_by_field_name("alias") if name.type == "aliased_import" else name.named_child(0)
                if bound is not None:
                    yield node_text(bound)


def _ecmascript_member(node: Node) -> bool:
    return _is_name_of(node, ECMASCRIPT_MEMBERS)


def _ecmascript_imports(root: Node) -> Iterator[str]:
    for clause in nodes(root):
        if clause.type != "import_clause":
            continue
        for child in clause.named_children:
            if child.type == "identifier":
                yield node_text(child)
            elif child.type == "namespace_import" and (name := child.named_child(0)) is not None:
                yield node_text(name)
            elif child.type == "named_imports":
                for specifier in child.named_children:
                    bound = specifier.child_by_field_name("alias") or specifier.child_by_field_name("name")
                    if bound is not None:
                        yield node_text(bound)


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


def _go_member(node: Node) -> bool:
    return _is_name_of(node, GO_MEMBERS)


def _go_imports(root: Node) -> Iterator[str]:
    for spec in nodes(root):
        if spec.type != "import_spec":
            continue
        name, path = spec.child_by_field_name("name"), spec.child_by_field_name("path")
        if name is not None:
            yield node_text(name)
        elif path is not None:
            yield _go_package(node_text(path).strip('"`'))


def _go_package(path: str) -> str:
    parts = path.split("/")
    last = parts[-2] if len(parts) > 1 and GO_MAJOR_VERSION.fullmatch(parts[-1]) else parts[-1]
    return last.split(".")[0]


def _parent_type(node: Node) -> str | None:
    return node.parent.type if node.parent else None


PYTHON = SourceLanguage("python", python.PYTHON, frozenset({"identifier"}), _python_definition, _python_member, _python_imports)
TYPESCRIPT = SourceLanguage(
    "ecmascript", TYPESCRIPT_EXTRACTOR.language, ECMASCRIPT_IDENTIFIERS, _ecmascript_definition, _ecmascript_member, _ecmascript_imports
)
TSX = SourceLanguage("ecmascript", TSX_EXTRACTOR.language, ECMASCRIPT_IDENTIFIERS, _ecmascript_definition, _ecmascript_member, _ecmascript_imports)
JAVASCRIPT = SourceLanguage(
    "ecmascript", JAVASCRIPT_EXTRACTOR.language, ECMASCRIPT_IDENTIFIERS, _ecmascript_definition, _ecmascript_member, _ecmascript_imports
)
GO = SourceLanguage("go", go.GO, frozenset({"identifier", "field_identifier", "type_identifier"}), _go_definition, _go_member, _go_imports)

LANGUAGES_BY_EXTRACTOR: dict[str, SourceLanguage] = {"python": PYTHON, "typescript": TYPESCRIPT, "tsx": TSX, "javascript": JAVASCRIPT, "go": GO}


def language_for(path: str) -> SourceLanguage | None:
    extractor = extractor_for(path)
    return LANGUAGES_BY_EXTRACTOR.get(extractor.name) if extractor else None


def file_symbols(language: SourceLanguage, source: bytes) -> FileSymbols:
    definitions: list[Symbol] = []
    used: set[str] = set()
    for symbol in _symbols(language, parse(language, source)):
        if symbol.definition:
            definitions.append(symbol)
        else:
            used.add(symbol.name)
    return FileSymbols(tuple(definitions), tuple(sorted(used)))


def references(language: SourceLanguage, source: bytes, name: str) -> list[Symbol]:
    wanted = name.encode()
    return [symbol_of(language, node) for node in _identifiers(language, parse(language, source)) if node.text == wanted and not language.is_definition(node)]


def symbol_at(language: SourceLanguage, source: bytes, row: int, column: int) -> Symbol | None:
    node = identifier_at(language, parse(language, source), row, column)
    return symbol_of(language, node) if node is not None else None


def identifier_at(language: SourceLanguage, tree: Tree, row: int, column: int) -> Node | None:
    for candidate in (column, column - 1):
        if candidate < 0:
            continue
        node = tree.root_node.descendant_for_point_range((row, candidate), (row, candidate))
        if node is not None and node.type in language.identifiers and node.start_point[0] == row:
            return node
    return None


def parse(language: SourceLanguage, source: bytes) -> Tree:
    return Parser(language.grammar).parse(source)


def _symbols(language: SourceLanguage, tree: Tree) -> Iterator[Symbol]:
    return (symbol_of(language, node) for node in _identifiers(language, tree))


def _identifiers(language: SourceLanguage, tree: Tree) -> Iterator[Node]:
    return (node for node in nodes(tree.root_node) if node.type in language.identifiers and node.start_point[0] == node.end_point[0])


def symbol_of(language: SourceLanguage, node: Node) -> Symbol:
    row, start = node.start_point
    definition = language.is_definition(node)
    return Symbol(node_text(node), row, start, definition, definition and language.is_member_definition(node))


def is_member(node: Node) -> bool:
    parent = node.parent
    return node.type in MEMBER_IDENTIFIERS or (parent is not None and parent.type == "attribute" and parent.child_by_field_name("attribute") == node)


def receiver_root(node: Node) -> Node | None:
    access = node.parent
    if access is None or access.type not in RECEIVERS:
        return None
    receiver = access.child_by_field_name(RECEIVERS[access.type])
    while receiver is not None and receiver.type in RECEIVERS:
        receiver = receiver.child_by_field_name(RECEIVERS[receiver.type])
    return receiver


def imported_names(language: SourceLanguage, node: Node) -> frozenset[str]:
    root = node
    while root.parent is not None:
        root = root.parent
    return frozenset(language.imports(root))


def nodes(root: Node) -> Iterator[Node]:
    cursor = root.walk()
    while True:
        if cursor.node is not None:
            yield cursor.node
        if cursor.goto_first_child():
            continue
        while not cursor.goto_next_sibling():
            if not cursor.goto_parent():
                return
