import gc
from pathlib import Path

import pytest

from rtool.units.registry import extractor_for

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
