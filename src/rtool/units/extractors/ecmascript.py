from tree_sitter import Language, Node

from rtool.units.extractors.base import SourceLines, Span, build_units
from rtool.units.extractors.treesitter import node_text, parse, span_for, with_name
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
    declaration = _unwrap_export(siblings[index])
    if declaration is None:
        return None
    kind = declaration.type
    name_node = declaration.child_by_field_name("name")
    if kind in FUNCTION_DECLARATIONS or kind in FUNCTION_VALUES:
        span = span_for(siblings, index, UnitKind.FUNCTION, _declared_name(declaration))
    elif kind in CLASS_DECLARATIONS:
        name = _declared_name(declaration)
        span = span_for(siblings, index, UnitKind.CLASS, name, _methods(declaration.child_by_field_name("body"), name))
    elif kind in TYPE_DECLARATIONS:
        span = span_for(siblings, index, UnitKind.TYPE, _declared_name(declaration))
    elif kind in VARIABLE_DECLARATIONS and (variable := _function_variable(declaration)) is not None:
        name_node = variable
        span = span_for(siblings, index, UnitKind.FUNCTION, node_text(variable))
    else:
        return None
    return with_name(span, name_node)


def _unwrap_export(node: Node) -> Node | None:
    if node.type != EXPORT_STATEMENT:
        return node
    return node.child_by_field_name("declaration") or node.child_by_field_name("value")


def _declared_name(declaration: Node) -> str:
    return node_text(declaration.child_by_field_name("name")) or DEFAULT_EXPORT_NAME


def _function_variable(declaration: Node) -> Node | None:
    declarators = [child for child in declaration.named_children if child.type == VARIABLE_DECLARATOR]
    if len(declarators) != 1:
        return None
    name = declarators[0].child_by_field_name("name")
    value = declarators[0].child_by_field_name("value")
    if name is None or name.type != IDENTIFIER or value is None or value.type not in FUNCTION_VALUES:
        return None
    return name


def _methods(body: Node | None, class_name: str) -> tuple[Span, ...]:
    if body is None:
        return ()
    siblings = body.named_children
    return tuple(
        with_name(span_for(siblings, index, UnitKind.METHOD, f"{class_name}.{_method_name(node)}"), node.child_by_field_name("name"))
        for index, node in enumerate(siblings)
        if node.type == METHOD_DEFINITION
    )


def _method_name(node: Node) -> str:
    accessor = next((child.type for child in node.children if not child.is_named and child.type in ACCESSOR_KEYWORDS), None)
    name = node_text(node.child_by_field_name("name"))
    return f"{accessor} {name}" if accessor else name
