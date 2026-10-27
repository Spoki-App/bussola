from typing import Any

from sqlalchemy.orm import Session

from rtool.storage.models import ParsedBlob
from rtool.units.extract import CacheKey
from rtool.units.model import Unit, UnitKind


class SqlUnitCache:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, key: CacheKey) -> list[Unit] | None:
        row = self._session.get(ParsedBlob, (key.object_id, key.extractor, key.version))
        return None if row is None else [_unit_from_json(item) for item in row.units]

    def put(self, key: CacheKey, units: list[Unit]) -> None:
        self._session.merge(ParsedBlob(key.object_id, key.extractor, key.version, [_unit_to_json(unit) for unit in units]))


def _unit_to_json(unit: Unit) -> dict[str, Any]:
    return {
        "kind": unit.kind.value,
        "qualified_name": unit.qualified_name,
        "text": unit.text,
        "content_hash": unit.content_hash,
        "line_numbers": list(unit.line_numbers),
    }


def _unit_from_json(data: dict[str, Any]) -> Unit:
    return Unit(UnitKind(data["kind"]), data["qualified_name"], data["text"], data["content_hash"], tuple(data["line_numbers"]))
