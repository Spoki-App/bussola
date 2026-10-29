import tree_sitter_go
from tree_sitter import Language, Node

from rtool.units.extractors.base import SourceLines, Span, build_units
from rtool.units.extractors.treesitter import node_text, parse, span_for, with_name
from rtool.units.model import Unit, UnitKind

GO = Language(tree_sitter_go.language())
FUNCTION_DECLARATION = "function_declaration"
METHOD_DECLARATION = "method_declaration"
TYPE_DECLARATION = "type_declaration"
TYPE_SPECS = frozenset({"type_spec", "type_alias"})
RECEIVER_WRAPPERS = frozenset({"pointer_type", "parenthesized_type"})
GENERIC_TYPE = "generic_type"
PARAMETER_DECLARATION = "parameter_declaration"


class GoExtractor:
    name: str = "go"
    version: int = 1

    def extract(self, source: bytes) -> list[Unit] | None:
        tree = parse(GO, source)
        if tree is None:
            return None
        return build_units(SourceLines.from_bytes(source), _collect(tree.root_node.named_children))


def _collect(siblings: list[Node]) -> list[Span]:
    spans: list[Span] = []
    for index, node in enumerate(siblings):
        name_node = node.child_by_field_name("name")
        if node.type == FUNCTION_DECLARATION:
            spans.append(with_name(span_for(siblings, index, UnitKind.FUNCTION, node_text(name_node)), name_node))
        elif node.type == METHOD_DECLARATION:
            name = f"{_receiver_type(node)}.{node_text(name_node)}".lstrip(".")
            spans.append(with_name(span_for(siblings, index, UnitKind.METHOD, name), name_node))
        elif node.type == TYPE_DECLARATION:
            spans.extend(_types(siblings, index))
    return spans


def _types(siblings: list[Node], index: int) -> list[Span]:
    declaration = siblings[index]
    specs = [child for child in declaration.named_children if child.type in TYPE_SPECS]
    if len(specs) == 1 and declaration.start_point.row == specs[0].start_point.row:
        name_node = specs[0].child_by_field_name("name")
        return [with_name(span_for(siblings, index, UnitKind.TYPE, node_text(name_node)), name_node)]
    members = declaration.named_children
    return [
        with_name(span_for(members, position, UnitKind.TYPE, node_text(member.child_by_field_name("name"))), member.child_by_field_name("name"))
        for position, member in enumerate(members)
        if member.type in TYPE_SPECS
    ]


def _receiver_type(method: Node) -> str:
    receiver = method.child_by_field_name("receiver")
    parameter = next((child for child in receiver.named_children if child.type == PARAMETER_DECLARATION), None) if receiver else None
    node = parameter.child_by_field_name("type") if parameter else None
    while node is not None and node.type in RECEIVER_WRAPPERS:
        node = node.named_children[0] if node.named_children else None
    if node is not None and node.type == GENERIC_TYPE:
        node = node.child_by_field_name("type")
    return node_text(node)
