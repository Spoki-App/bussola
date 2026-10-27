from tree_sitter import Language, Node

from rtool.units.extractors.base import SourceLines, Span, build_units
from rtool.units.extractors.treesitter import node_text, parse, span_for
from rtool.units.model import Unit, UnitKind

EXPORT_STATEMENT = "export_statement"
VARIABLE_DECLARATOR = "variable_declarator"
METHOD_DEFINITION = "method_definition"
IDENTIFIER = "identifier"
ACCESSOR_KEYWORDS = frozenset({"get", "set"})
DEFAULT_EXPORT_NAME = "default"
FUNCTION_DECLARATIONS = frozenset({"function_declaration", "generator_function_declaration", "function_signature"})
FUNCTION_VALUES = frozenset({"arrow_function", "function_expression", "generator_function", "function"})
CLASS_DECLARATIONS = frozenset({"class_declaration", "abstract_class_declaration", "class"})
TYPE_DECLARATIONS = frozenset({"interface_declaration", "type_alias_declaration", "enum_declaration"})
VARIABLE_DECLARATIONS = frozenset({"lexical_declaration", "variable_declaration"})


class EcmaScriptExtractor:
    version: int = 1

    def __init__(self, name: str, language: Language) -> None:
        self.name: str = name
        self._language = language

    def extract(self, source: bytes) -> list[Unit] | None:
        root = parse(self._language, source)
        if root is None:
            return None
        siblings = root.named_children
        spans = [span for index in range(len(siblings)) if (span := _top_level_span(siblings, index)) is not None]
        return build_units(SourceLines.from_bytes(source), spans)


def _top_level_span(siblings: list[Node], index: int) -> Span | None:
    node = siblings[index]
    declaration = _unwrap_export(node)
    if declaration is None:
        return None
    kind = declaration.type
    if kind in FUNCTION_DECLARATIONS or kind in FUNCTION_VALUES:
        return span_for(siblings, index, UnitKind.FUNCTION, _declared_name(declaration))
    if kind in CLASS_DECLARATIONS:
        name = _declared_name(declaration)
        return span_for(siblings, index, UnitKind.CLASS, name, _methods(declaration.child_by_field_name("body"), name))
    if kind in TYPE_DECLARATIONS:
        return span_for(siblings, index, UnitKind.TYPE, _declared_name(declaration))
    if kind in VARIABLE_DECLARATIONS and (name := _function_variable_name(declaration)) is not None:
        return span_for(siblings, index, UnitKind.FUNCTION, name)
    return None


def _unwrap_export(node: Node) -> Node | None:
    if node.type != EXPORT_STATEMENT:
        return node
    return node.child_by_field_name("declaration") or node.child_by_field_name("value")


def _declared_name(declaration: Node) -> str:
    return node_text(declaration.child_by_field_name("name")) or DEFAULT_EXPORT_NAME


def _function_variable_name(declaration: Node) -> str | None:
    declarators = [child for child in declaration.named_children if child.type == VARIABLE_DECLARATOR]
    if len(declarators) != 1:
        return None
    name = declarators[0].child_by_field_name("name")
    value = declarators[0].child_by_field_name("value")
    if name is None or name.type != IDENTIFIER or value is None or value.type not in FUNCTION_VALUES:
        return None
    return node_text(name)


def _methods(body: Node | None, class_name: str) -> tuple[Span, ...]:
    if body is None:
        return ()
    siblings = body.named_children
    return tuple(
        span_for(siblings, index, UnitKind.METHOD, f"{class_name}.{_method_name(node)}")
        for index, node in enumerate(siblings)
        if node.type == METHOD_DEFINITION
    )


def _method_name(node: Node) -> str:
    accessor = next((child.type for child in node.children if not child.is_named and child.type in ACCESSOR_KEYWORDS), None)
    name = node_text(node.child_by_field_name("name"))
    return f"{accessor} {name}" if accessor else name
