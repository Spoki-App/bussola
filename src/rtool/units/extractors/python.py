import tree_sitter_python
from tree_sitter import Language, Node

from rtool.units.extractors.base import SourceLines, Span, build_units
from rtool.units.extractors.treesitter import node_text, parse, span_for, with_name
from rtool.units.model import Unit, UnitKind

PYTHON = Language(tree_sitter_python.language())
FUNCTION_DEFINITION = "function_definition"
CLASS_DEFINITION = "class_definition"
DECORATED_DEFINITION = "decorated_definition"


class PythonExtractor:
    name: str = "python"
    version: int = 1

    def extract(self, source: bytes) -> list[Unit] | None:
        tree = parse(PYTHON, source)
        if tree is None:
            return None
        return build_units(SourceLines.from_bytes(source), _collect(tree.root_node.named_children, "", in_class=False))


def _collect(siblings: list[Node], prefix: str, *, in_class: bool) -> list[Span]:
    spans: list[Span] = []
    for index, node in enumerate(siblings):
        definition = node.child_by_field_name("definition") if node.type == DECORATED_DEFINITION else node
        if definition is None:
            continue
        name_node = definition.child_by_field_name("name")
        name = prefix + node_text(name_node)
        if definition.type == FUNCTION_DEFINITION:
            spans.append(with_name(span_for(siblings, index, UnitKind.METHOD if in_class else UnitKind.FUNCTION, name), name_node))
        elif definition.type == CLASS_DEFINITION:
            body = definition.child_by_field_name("body")
            children = _collect(body.named_children, f"{name}.", in_class=True) if body else []
            spans.append(with_name(span_for(siblings, index, UnitKind.CLASS, name, tuple(children)), name_node))
    return spans
