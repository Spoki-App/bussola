from bussola.units.model import Unit, UnitKind
from bussola.units.registry import extractor_for


def extract(path: str, source: str) -> list[Unit]:
    extractor = extractor_for(path)
    assert extractor is not None
    units = extractor.extract(source.encode())
    assert units is not None
    return units


def names(units: list[Unit]) -> list[tuple[UnitKind, str]]:
    return [(unit.kind, unit.qualified_name) for unit in units]


def unit_named(units: list[Unit], kind: UnitKind, name: str) -> Unit:
    return next(unit for unit in units if unit.kind == kind and unit.qualified_name == name)
