import gc
from pathlib import Path

import pytest

from bussola.units.model import UnitKind
from bussola.units.registry import extractor_for
from tests.units.helpers import extract

PROJECT_ROOT = Path(__file__).parents[2]
SOURCES = sorted(
    path
    for folder in ("src", "tests", "frontend/src", "frontend/e2e")
    for path in (PROJECT_ROOT / folder).rglob("*")
    if path.is_file() and extractor_for(path.name) is not None
)


@pytest.mark.parametrize("path", SOURCES, ids=lambda path: str(path.relative_to(PROJECT_ROOT)))
def test_extracting_this_projects_sources_yields_units(path: Path) -> None:
    extractor = extractor_for(path.name)
    assert extractor is not None

    units = extractor.extract(path.read_bytes())
    gc.collect()

    assert units is not None
    assert all(unit.text is not None for unit in units)
    assert [unit.qualified_name for unit in units] == [unit.qualified_name for unit in units if unit.content_hash]


@pytest.mark.parametrize(
    ("path", "header", "function"),
    [
        ("big.py", "", "def f{index}(a):\n    return a"),
        ("big.ts", "", "export function f{index}(a: number) {{ return a }}"),
        ("big.go", "package main\n\n", "func F{index}() int {{ return {index} }}"),
    ],
)
def test_extracting_sources_with_rows_beyond_the_small_int_cache_is_stable(path: str, header: str, function: str) -> None:
    source = header + "\n\n".join(function.format(index=index) for index in range(400))

    for _ in range(3):
        units = extract(path, source)
        gc.collect()
        functions = [unit for unit in units if unit.kind == UnitKind.FUNCTION]
        assert len(functions) == 400
        assert functions[-1].line_numbers[-1] == len(source.splitlines())
