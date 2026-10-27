from tree_sitter import Language, Node, Parser

from rtool.units.extractors.base import NameLocation, Span
from rtool.units.model import UnitKind

COMMENT = "comment"


def parse(language: Language, source: bytes) -> Node | None:
    root = Parser(language).parse(source).root_node
    return None if root.has_error else root


def node_text(node: Node | None) -> str:
    if node is None or node.text is None:
        return ""
    return node.text.decode(errors="replace")


def last_row(node: Node) -> int:
    row = node.end_point.row
    return row - 1 if node.end_point.column == 0 and row > node.start_point.row else row


def span_for(siblings: list[Node], index: int, kind: UnitKind, qualified_name: str, children: tuple[Span, ...] = ()) -> Span:
    return Span(kind, qualified_name, _leading_comment_row(siblings, index), last_row(siblings[index]), children)


def with_name(span: Span, name_node: Node | None) -> Span:
    if name_node is None or name_node.start_point.row != name_node.end_point.row:
        return span
    location = NameLocation(name_node.start_point.row, name_node.start_point.column, name_node.end_point.column)
    return Span(span.kind, span.qualified_name, span.start_row, span.end_row, span.children, location)


def _leading_comment_row(siblings: list[Node], index: int) -> int:
    start = siblings[index].start_point.row
    position = index - 1
    while position >= 0:
        candidate = siblings[position]
        if candidate.type != COMMENT or last_row(candidate) != start - 1:
            break
        if position > 0 and last_row(siblings[position - 1]) == candidate.start_point.row:
            break
        start = candidate.start_point.row
        position -= 1
    return start
