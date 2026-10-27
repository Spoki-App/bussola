import tree_sitter_python
from tree_sitter import Language, Node

from rtool.units.extractors.base import SourceLines, Span, build_units
from rtool.units.extractors.treesitter import node_text, parse, span_for
from rtool.units.model import Unit, UnitKind

PYTHON = Language(tree_sitter_python.language())
FUNCTION_DEFINITION = "function_definition"
CLASS_DEFINITION = "class_definition"
DECORATED_DEFINITION = "decorated_definition"


class PythonExtractor:
    name: str = "python"
    version: int = 1

    def extract(self, source: bytes) -> list[Unit] | None:
        root = parse(PYTHON, source)
        if root is None:
            return None
        return build_units(SourceLines.from_bytes(source), _collect(root.named_children, "", in_class=False))


def _collect(siblings: list[Node], prefix: str, *, in_class: bool) -> list[Span]:
    spans: list[Span] = []
    for index, node in enumerate(siblings):
        definition = node.child_by_field_name("definition") if node.type == DECORATED_DEFINITION else node
        if definition is None:
            continue
        name = prefix + node_text(definition.child_by_field_name("name"))
        if definition.type == FUNCTION_DEFINITION:
            spans.append(span_for(siblings, index, UnitKind.METHOD if in_class else UnitKind.FUNCTION, name))
        elif definition.type == CLASS_DEFINITION:
            body = definition.child_by_field_name("body")
            children = _collect(body.named_children, f"{name}.", in_class=True) if body else []
            spans.append(span_for(siblings, index, UnitKind.CLASS, name, tuple(children)))
    return spans
