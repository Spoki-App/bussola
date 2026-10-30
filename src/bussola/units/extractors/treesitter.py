from tree_sitter import Language, Node, Parser, Tree

from bussola.units.extractors.base import NameLocation, Span
from bussola.units.model import UnitKind

COMMENT = "comment"


def parse(language: Language, source: bytes) -> Tree | None:
    tree = Parser(language).parse(source)
    return None if tree.root_node.has_error else tree


def node_text(node: Node | None) -> str:
    if node is None or node.text is None:
        return ""
    return node.text.decode(errors="replace")


def start_row(node: Node) -> int:
    row, _ = node.start_point
    return row


def last_row(node: Node) -> int:
    row, column = node.end_point
    return row - 1 if column == 0 and row > start_row(node) else row


def span_for(siblings: list[Node], index: int, kind: UnitKind, qualified_name: str, children: tuple[Span, ...] = ()) -> Span:
    return Span(kind, qualified_name, _leading_comment_row(siblings, index), last_row(siblings[index]), children)


def with_name(span: Span, name_node: Node | None) -> Span:
    if name_node is None:
        return span
    (row, start_column), (end_row, end_column) = name_node.start_point, name_node.end_point
    if row != end_row:
        return span
    location = NameLocation(row, start_column, end_column)
    return Span(span.kind, span.qualified_name, span.start_row, span.end_row, span.children, location)


def _leading_comment_row(siblings: list[Node], index: int) -> int:
    start = start_row(siblings[index])
    position = index - 1
    while position >= 0:
        candidate = siblings[position]
        if candidate.type != COMMENT or last_row(candidate) != start - 1:
            break
        if position > 0 and last_row(siblings[position - 1]) == start_row(candidate):
            break
        start = start_row(candidate)
        position -= 1
    return start
