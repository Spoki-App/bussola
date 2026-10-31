from typing import NamedTuple

import pytest

from bussola.navigation.positions import byte_to_utf16, utf16_to_byte
from bussola.navigation.symbols import FileSymbols, SourceLanguage, file_symbols, language_for, references, symbol_at

PYTHON_SOURCE = """LIMIT = 3
A = B = 4


class Cart:
    size = 1

    def total(self, items):
        local = LIMIT
        return helper(items) + local


def helper(items):
    return len(items)


def main():
    Cart().total([])
"""

TYPESCRIPT_SOURCE = """export const LIMIT = 3
const tax = (amount: number) => amount * LIMIT

export interface Priced {
  price(): number
}

export type Amount = number

enum Currency { Euro }

export class Cart implements Priced {
  price(): number {
    return tax(LIMIT)
  }
}

export function total(cart: Cart): Amount {
  const inner = 1
  return cart.price() + inner
}
"""

TSX_SOURCE = """export function Badge({ label }: { label: string }) {
  return <span>{label}</span>
}

export const Page = () => <Badge label="x" />
"""

JAVASCRIPT_SOURCE = """const LIMIT = 3

function* ids() {
  yield LIMIT
}

class Cart {
  total() {
    return ids()
  }
}

module.exports = { Cart }
"""

GO_SOURCE = """package cart

var (
\tlimit = 3
\tfirst, second int
)

const Rate = 2

type Cart struct {
\tItems []int
}

type Alias = Cart

func (c *Cart) Total() int {
\tlocal := limit
\treturn local * Rate
}

func New() *Cart {
\tc := &Cart{}
\tc.Total()
\treturn c
}
"""


def symbols_of(path: str, source: str) -> FileSymbols:
    return file_symbols(language(path), source.encode())


def language(path: str) -> SourceLanguage:
    found = language_for(path)
    assert found is not None
    return found


def definitions(path: str, source: str) -> list[tuple[str, int]]:
    return [(symbol.name, symbol.row + 1) for symbol in symbols_of(path, source).definitions]


def usages(path: str, source: str, name: str) -> list[int]:
    return [symbol.row + 1 for symbol in references(language(path), source.encode(), name)]


def test_python_definitions_are_functions_methods_classes_and_module_variables() -> None:
    assert definitions("cart.py", PYTHON_SOURCE) == [("LIMIT", 1), ("A", 2), ("B", 2), ("Cart", 5), ("total", 8), ("helper", 13), ("main", 17)]


def test_python_references_include_calls_attributes_and_names_but_not_definitions() -> None:
    assert usages("cart.py", PYTHON_SOURCE, "helper") == [10]
    assert usages("cart.py", PYTHON_SOURCE, "total") == [18]
    assert usages("cart.py", PYTHON_SOURCE, "LIMIT") == [9]
    assert "local" in symbols_of("cart.py", PYTHON_SOURCE).used_names
    assert "size" in symbols_of("cart.py", PYTHON_SOURCE).used_names


def test_typescript_definitions_cover_declarations_methods_types_and_module_constants() -> None:
    assert definitions("cart.ts", TYPESCRIPT_SOURCE) == [
        ("LIMIT", 1),
        ("tax", 2),
        ("Priced", 4),
        ("price", 5),
        ("Amount", 8),
        ("Currency", 10),
        ("Cart", 12),
        ("price", 13),
        ("total", 18),
    ]


def test_typescript_references_follow_calls_members_and_types() -> None:
    assert usages("cart.ts", TYPESCRIPT_SOURCE, "LIMIT") == [2, 14]
    assert usages("cart.ts", TYPESCRIPT_SOURCE, "price") == [20]
    assert usages("cart.ts", TYPESCRIPT_SOURCE, "Cart") == [18]
    assert usages("cart.ts", TYPESCRIPT_SOURCE, "Amount") == [18]
    assert usages("cart.ts", TYPESCRIPT_SOURCE, "inner") == [19, 20]


def test_tsx_components_are_definitions_and_jsx_tags_are_references() -> None:
    assert definitions("badge.tsx", TSX_SOURCE) == [("Badge", 1), ("Page", 5)]
    assert usages("badge.tsx", TSX_SOURCE, "Badge") == [5]
    assert usages("badge.tsx", TSX_SOURCE, "label") == [1, 1, 2, 5]


def test_javascript_definitions_and_references() -> None:
    assert definitions("cart.js", JAVASCRIPT_SOURCE) == [("LIMIT", 1), ("ids", 3), ("Cart", 7), ("total", 8)]
    assert usages("cart.js", JAVASCRIPT_SOURCE, "ids") == [9]
    assert usages("cart.js", JAVASCRIPT_SOURCE, "Cart") == [13]


def test_go_definitions_cover_functions_methods_types_and_package_variables() -> None:
    assert definitions("cart.go", GO_SOURCE) == [
        ("limit", 4),
        ("first", 5),
        ("second", 5),
        ("Rate", 8),
        ("Cart", 10),
        ("Alias", 14),
        ("Total", 16),
        ("New", 21),
    ]


def test_go_references_follow_selectors_types_and_variables() -> None:
    assert usages("cart.go", GO_SOURCE, "Total") == [23]
    assert usages("cart.go", GO_SOURCE, "Cart") == [14, 16, 21, 22]
    assert usages("cart.go", GO_SOURCE, "limit") == [17]


class Click(NamedTuple):
    path: str
    source: str
    line: int
    text: str
    name: str
    definition: bool


@pytest.mark.parametrize(
    "click",
    [
        Click("cart.py", PYTHON_SOURCE, 10, "helper(", "helper", False),
        Click("cart.py", PYTHON_SOURCE, 13, "helper(", "helper", True),
        Click("cart.ts", TYPESCRIPT_SOURCE, 14, "tax(", "tax", False),
        Click("cart.ts", TYPESCRIPT_SOURCE, 18, "total(", "total", True),
        Click("badge.tsx", TSX_SOURCE, 5, "Badge label", "Badge", False),
        Click("cart.js", JAVASCRIPT_SOURCE, 9, "ids(", "ids", False),
        Click("cart.go", GO_SOURCE, 23, "Total(", "Total", False),
        Click("cart.go", GO_SOURCE, 16, "Total(", "Total", True),
    ],
)
def test_symbol_at_finds_the_identifier_under_the_cursor(click: Click) -> None:
    row = click.line - 1
    column = click.source.split("\n")[row].index(click.text) + 1

    symbol = symbol_at(language(click.path), click.source.encode(), row, column)

    assert symbol is not None
    assert (symbol.name, symbol.definition) == (click.name, click.definition)


def test_symbol_at_accepts_a_click_just_after_the_name() -> None:
    row = 9
    column = PYTHON_SOURCE.split("\n")[row].index("helper") + len("helper")

    symbol = symbol_at(language("cart.py"), PYTHON_SOURCE.encode(), row, column)

    assert symbol is not None
    assert symbol.name == "helper"


def test_symbol_at_ignores_keywords_strings_and_blank_space() -> None:
    source = b'def run():\n    return "helper"\n'

    assert symbol_at(language("run.py"), source, 1, 6) is None
    assert symbol_at(language("run.py"), source, 1, 13) is None
    assert symbol_at(language("run.py"), source, 1, 1) is None


def test_unsupported_files_have_no_language() -> None:
    assert language_for("README.md") is None


def test_columns_convert_between_utf16_and_utf8() -> None:
    line = "s = 'café \U0001f600' + name".encode()
    utf16_column = len("s = 'café \U0001f600' + ".encode("utf-16-le")) // 2
    byte_column = line.index(b"name")

    assert utf16_to_byte(line, utf16_column) == byte_column
    assert byte_to_utf16(line, byte_column) == utf16_column
