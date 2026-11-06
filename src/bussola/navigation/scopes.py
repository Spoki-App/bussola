from collections.abc import Callable, Iterator
from dataclasses import dataclass

from tree_sitter import Node

from bussola.units.extractors import ecmascript, go, python
from bussola.units.extractors.treesitter import node_text
from bussola.units.model import UnitKind


@dataclass(frozen=True)
class Enclosing:
    kind: UnitKind
    qualified_name: str


@dataclass(frozen=True)
class Scope:
    kind: UnitKind
    name: str
    body: Node | None


MODULE_LEVEL = Enclosing(UnitKind.MODULE, "")


def enclosing_at(family: str, root: Node, row: int, column: int) -> Enclosing:
    target = root.descendant_for_point_range((row, column), (row, column))
    if target is None:
        return MODULE_LEVEL
    scope_of = SCOPE_RULES[family]
    scopes = [scope for ancestor in _ancestors(target) if (scope := scope_of(ancestor)) is not None and _contains(scope.body, target)]
    if not scopes:
        return MODULE_LEVEL
    name = ".".join(scope.name for scope in reversed(scopes))
    in_class = len(scopes) > 1 and scopes[1].kind == UnitKind.CLASS
    kind = UnitKind.METHOD if scopes[0].kind == UnitKind.FUNCTION and in_class else scopes[0].kind
    return Enclosing(kind, name)


def _ancestors(node: Node) -> Iterator[Node]:
    current = node.parent
    while current is not None:
        yield current
        current = current.parent


def _contains(body: Node | None, target: Node) -> bool:
    return body is not None and body.start_byte <= target.start_byte and target.end_byte <= body.end_byte


def _python_scope(node: Node) -> Scope | None:
    kinds = {python.FUNCTION_DEFINITION: UnitKind.FUNCTION, python.CLASS_DEFINITION: UnitKind.CLASS}
    kind = kinds.get(node.type)
    return Scope(kind, node_text(node.child_by_field_name("name")), node.child_by_field_name("body")) if kind else None


def _go_scope(node: Node) -> Scope | None:
    name = node_text(node.child_by_field_name("name"))
    if node.type == go.FUNCTION_DECLARATION:
        return Scope(UnitKind.FUNCTION, name, node.child_by_field_name("body"))
    if node.type == go.METHOD_DECLARATION:
        return Scope(UnitKind.METHOD, f"{go.receiver_type(node)}.{name}".lstrip("."), node.child_by_field_name("body"))
    if node.type in go.TYPE_SPECS:
        return Scope(UnitKind.TYPE, name, node.child_by_field_name("type"))
    return None


def _ecmascript_scope(node: Node) -> Scope | None:
    body = node.child_by_field_name("body") or node.child_by_field_name("value")
    if node.type == ecmascript.METHOD_DEFINITION:
        return Scope(UnitKind.METHOD, ecmascript.method_name(node), body)
    kind = _ecmascript_kind(node.type)
    name = _ecmascript_name(node) if kind else None
    return Scope(kind, name, body) if kind and name else None


def _ecmascript_kind(node_type: str) -> UnitKind | None:
    if node_type in ecmascript.FUNCTION_DECLARATIONS or node_type in ecmascript.FUNCTION_VALUES:
        return UnitKind.FUNCTION
    if node_type in ecmascript.CLASS_DECLARATIONS:
        return UnitKind.CLASS
    return UnitKind.TYPE if node_type in ecmascript.TYPE_DECLARATIONS else None


def _ecmascript_name(node: Node) -> str | None:
    if (name := node.child_by_field_name("name")) is not None:
        return node_text(name)
    parent = node.parent
    if parent is not None and parent.type == ecmascript.VARIABLE_DECLARATOR:
        variable = parent.child_by_field_name("name")
        return node_text(variable) if variable is not None and variable.type == ecmascript.IDENTIFIER else None
    return ecmascript.DEFAULT_EXPORT_NAME if parent is not None and parent.type == ecmascript.EXPORT_STATEMENT else None


SCOPE_RULES: dict[str, Callable[[Node], Scope | None]] = {"python": _python_scope, "go": _go_scope, "ecmascript": _ecmascript_scope}
