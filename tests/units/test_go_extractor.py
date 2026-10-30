from bussola.units.model import UnitKind
from bussola.units.normalize import UNIT_PLACEHOLDER
from bussola.units.registry import extractor_for
from tests.units.helpers import extract, names, unit_named

SOURCE = """package billing

import "fmt"

// Service charges customers.
type Service struct {
\tName string
}

type (
\t// Reader reads.
\tReader interface{ Read() }
\tCelsius float64
\tAlias = Service
)

type Stack[T any] struct{ items []T }

// Run charges once.
func (s *Service) Run(ctx context.Context) error {
\treturn nil
}

func (s Stack[T]) Push(v T) {}

func (Celsius) String() string { return fmt.Sprint(1) }

func New() *Service { return nil }

var limit = 3
"""


def test_go_units_cover_types_methods_functions_and_module() -> None:
    units = extract("billing.go", SOURCE)

    assert names(units) == [
        (UnitKind.MODULE, ""),
        (UnitKind.TYPE, "Service"),
        (UnitKind.TYPE, "Reader"),
        (UnitKind.TYPE, "Celsius"),
        (UnitKind.TYPE, "Alias"),
        (UnitKind.TYPE, "Stack"),
        (UnitKind.METHOD, "Service.Run"),
        (UnitKind.METHOD, "Stack.Push"),
        (UnitKind.METHOD, "Celsius.String"),
        (UnitKind.FUNCTION, "New"),
    ]


def test_method_unit_starts_at_its_doc_comment() -> None:
    method = unit_named(extract("billing.go", SOURCE), UnitKind.METHOD, "Service.Run")

    assert method.text == "// Run charges once.\nfunc (s *Service) Run(ctx context.Context) error {\n\treturn nil\n}"


def test_grouped_types_are_separate_units_and_the_group_stays_in_module() -> None:
    units = extract("billing.go", SOURCE)
    module = unit_named(units, UnitKind.MODULE, "")

    assert unit_named(units, UnitKind.TYPE, "Reader").text == "\t// Reader reads.\n\tReader interface{ Read() }"
    assert module.text == f'package billing\n\nimport "fmt"\n{UNIT_PLACEHOLDER}\ntype (\n{UNIT_PLACEHOLDER}\n)\n{UNIT_PLACEHOLDER}\nvar limit = 3\n'


def test_renaming_a_method_keeps_its_hash() -> None:
    renamed = SOURCE.replace(") Run(", ") Charge(")

    before = unit_named(extract("billing.go", SOURCE), UnitKind.METHOD, "Service.Run")
    after = unit_named(extract("billing.go", renamed), UnitKind.METHOD, "Service.Charge")

    assert before.content_hash == after.content_hash


def test_repeated_init_functions_get_positional_suffixes() -> None:
    source = "package main\n\nfunc init() {}\n\nfunc init() {}\n"

    assert names(extract("main.go", source)) == [(UnitKind.MODULE, ""), (UnitKind.FUNCTION, "init"), (UnitKind.FUNCTION, "init#2")]


def test_go_syntax_error_returns_none_for_fallback() -> None:
    extractor = extractor_for("broken.go")

    assert extractor is not None
    assert extractor.extract(b"package main\n\nfunc broken( {\n") is None
