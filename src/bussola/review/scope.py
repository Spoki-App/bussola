from dataclasses import dataclass
from enum import StrEnum

from bussola.git import BlobReader, FileChange, GitRepo
from bussola.globs import matches_any
from bussola.units.extract import FileUnitExtractor
from bussola.units.model import Unit, UnitKey, UnitKind

type UnitIdentity = tuple[UnitKind, str]


class ChangeType(StrEnum):
    ADDED = "added"
    MODIFIED = "modified"
    REMOVED = "removed"


@dataclass(frozen=True)
class UnitChange:
    key: UnitKey
    old_path: str | None
    base: Unit | None
    head: Unit | None

    @property
    def base_hash(self) -> str | None:
        return self.base.content_hash if self.base else None

    @property
    def head_hash(self) -> str | None:
        return self.head.content_hash if self.head else None

    @property
    def change_type(self) -> ChangeType:
        if self.base is None:
            return ChangeType.ADDED
        return ChangeType.REMOVED if self.head is None else ChangeType.MODIFIED


def compute_scope(repo: GitRepo, base_sha: str, head_sha: str, extractor: FileUnitExtractor) -> list[UnitChange]:
    ignore = extractor.config.ignore
    changes = [change for change in repo.changed_files(base_sha, head_sha) if not _is_ignored(change, ignore)]
    scope: list[UnitChange] = []
    with repo.blob_reader() as reader:
        for change in changes:
            scope.extend(_file_scope(change, extractor, reader))
    return scope


def _is_ignored(change: FileChange, ignore: tuple[str, ...]) -> bool:
    return any(ref is not None and matches_any(ref.path, ignore) for ref in (change.old, change.new))


def _file_scope(change: FileChange, extractor: FileUnitExtractor, reader: BlobReader) -> list[UnitChange]:
    base_units = _by_identity(extractor.units_for(change.old, reader)) if change.old else {}
    head_units = _by_identity(extractor.units_for(change.new, reader)) if change.new else {}
    renamed = change.old is not None and change.new is not None and change.old.path != change.new.path
    old_path = change.old.path if renamed and change.old else None
    identities = list(head_units) + [identity for identity in base_units if identity not in head_units]
    return [
        UnitChange(UnitKey(change.path, kind, name), old_path, base_units.get((kind, name)), head_units.get((kind, name)))
        for kind, name in identities
        if _hash(base_units.get((kind, name))) != _hash(head_units.get((kind, name)))
    ]


def _by_identity(units: list[Unit]) -> dict[UnitIdentity, Unit]:
    return {(unit.kind, unit.qualified_name): unit for unit in units}


def _hash(unit: Unit | None) -> str | None:
    return unit.content_hash if unit else None
