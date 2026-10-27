from rtool.units.model import UnitKind
from rtool.units.normalize import UNIT_PLACEHOLDER
from rtool.units.registry import extractor_for
from tests.units.helpers import extract, names, unit_named

SOURCE = '''import os

LIMIT = 3


# Explains f.
@cache
async def f(x):
    def inner():
        return x
    return inner


class Service(Base):
    """Docs."""

    retries = LIMIT

    @property
    def name(self):
        return "s"

    class Config:
        def load(self):
            return {}


print("loaded")
'''


def test_python_units_cover_functions_classes_methods_and_module() -> None:
    units = extract("app.py", SOURCE)

    assert names(units) == [
        (UnitKind.MODULE, ""),
        (UnitKind.FUNCTION, "f"),
        (UnitKind.CLASS, "Service"),
        (UnitKind.METHOD, "Service.name"),
        (UnitKind.CLASS, "Service.Config"),
        (UnitKind.METHOD, "Service.Config.load"),
    ]


def test_function_unit_starts_at_leading_comment_and_includes_nested_functions() -> None:
    function = unit_named(extract("app.py", SOURCE), UnitKind.FUNCTION, "f")

    assert function.text is not None
    assert function.text.splitlines()[:2] == ["# Explains f.", "@cache"]
    assert "def inner" in function.text
    assert (function.start_line, function.end_line) == (6, 11)


def test_class_unit_excludes_methods_and_nested_classes() -> None:
    service = unit_named(extract("app.py", SOURCE), UnitKind.CLASS, "Service")

    assert service.text == f'class Service(Base):\n    """Docs."""\n\n    retries = LIMIT\n{UNIT_PLACEHOLDER}'


def test_module_unit_replaces_each_block_of_units_with_one_placeholder() -> None:
    module = unit_named(extract("app.py", SOURCE), UnitKind.MODULE, "")

    assert module.text == f'import os\n\nLIMIT = 3\n{UNIT_PLACEHOLDER}\nprint("loaded")\n'


def test_overloads_with_the_same_name_get_positional_suffixes() -> None:
    source = "@overload\ndef f(x: int) -> int: ...\n@overload\ndef f(x: str) -> str: ...\ndef f(x): return x\n"

    assert names(extract("api.pyi", source)) == [(UnitKind.FUNCTION, "f"), (UnitKind.FUNCTION, "f#2"), (UnitKind.FUNCTION, "f#3")]


def test_syntax_error_returns_none_for_fallback() -> None:
    extractor = extractor_for("broken.py")

    assert extractor is not None
    assert extractor.extract(b"def broken(:\n    pass\n") is None
