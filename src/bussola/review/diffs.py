from dataclasses import dataclass
from enum import StrEnum

from bussola.review.rows import ROW_APPROVABLE_KINDS, LineChange, Side, UnitLine, changed_rows, diff_lines, is_binary, side_lines, unit_lines
from bussola.storage.models import Approval, UnitSnapshot
from bussola.units.model import UnitKind
from bussola.units.normalize import UNIT_PLACEHOLDER

PLACEHOLDER_LABEL = "\u22ef"


class DiffMode(StrEnum):
    BASE = "base"
    APPROVED = "approved"


@dataclass(frozen=True)
class DiffRow:
    change: LineChange
    old_index: int | None
    new_index: int | None
    old_line: int | None
    new_line: int | None
    text: str
    row_hash: str | None = None
    placeholder: bool = False


@dataclass(frozen=True)
class UnitDiff:
    mode: DiffMode
    rows: list[DiffRow]
    unified: str
    binary: bool


@dataclass(frozen=True)
class DiffChoice:
    effective: DiffMode
    available: list[DiffMode]
    approved_text_unavailable: bool


def choose_diff_mode(snapshot: UnitSnapshot, approval: Approval | None, requested: DiffMode | None) -> DiffChoice:
    has_text = approval is not None and approval.approved_text is not None
    available = [DiffMode.BASE, DiffMode.APPROVED] if approval is not None and approval.head_hash != snapshot.head_hash else [DiffMode.BASE]
    wanted = requested or (DiffMode.APPROVED if DiffMode.APPROVED in available and has_text else DiffMode.BASE)
    effective = wanted if wanted == DiffMode.BASE or has_text else DiffMode.BASE
    return DiffChoice(effective, available, wanted == DiffMode.APPROVED and not has_text)


def build_diff(snapshot: UnitSnapshot, mode: DiffMode, approval: Approval | None) -> UnitDiff:
    new = side_lines(snapshot, Side.HEAD)
    if mode == DiffMode.APPROVED and approval is not None:
        approved = unit_lines(approval.approved_text, [])
        old = [UnitLine(line.text, index + 1) for index, line in enumerate(approved)]
    else:
        old = side_lines(snapshot, Side.BASE)
    rows = _rows(old, new, with_hashes=mode == DiffMode.BASE and UnitKind(snapshot.kind) in ROW_APPROVABLE_KINDS)
    rows = [_labelled(row) for row in rows]
    return UnitDiff(mode, rows, _unified(snapshot.old_path or snapshot.path, snapshot.path, rows), is_binary(snapshot))


def _labelled(row: DiffRow) -> DiffRow:
    if row.text != UNIT_PLACEHOLDER:
        return row
    return DiffRow(row.change, row.old_index, row.new_index, row.old_line, row.new_line, PLACEHOLDER_LABEL, row.row_hash, placeholder=True)


def _rows(old: list[UnitLine], new: list[UnitLine], *, with_hashes: bool) -> list[DiffRow]:
    old_texts = [line.text for line in old]
    new_texts = [line.text for line in new]
    lines = diff_lines(old_texts, new_texts)
    hashes = {(row.side, row.index): row.row_hash for row in changed_rows(old_texts, new_texts, lines)} if with_hashes else {}
    rows: list[DiffRow] = []
    for line in lines:
        old_line = old[line.old_index].file_line if line.old_index is not None else None
        new_line = new[line.new_index].file_line if line.new_index is not None else None
        row_hash = None
        if line.change == LineChange.ADDED and line.new_index is not None:
            row_hash = hashes.get((Side.HEAD, line.new_index))
        elif line.change == LineChange.REMOVED and line.old_index is not None:
            row_hash = hashes.get((Side.BASE, line.old_index))
        rows.append(DiffRow(line.change, line.old_index, line.new_index, old_line, new_line, line.text, row_hash))
    return rows


def _unified(old_path: str, new_path: str, rows: list[DiffRow]) -> str:
    old_count = sum(1 for row in rows if row.change != LineChange.ADDED)
    new_count = sum(1 for row in rows if row.change != LineChange.REMOVED)
    prefixes = {LineChange.CONTEXT: " ", LineChange.ADDED: "+", LineChange.REMOVED: "-"}
    header = [
        f"diff --git a/{old_path} b/{new_path}",
        f"--- a/{old_path}",
        f"+++ b/{new_path}",
        f"@@ -{1 if old_count else 0},{old_count} +{1 if new_count else 0},{new_count} @@",
    ]
    return "\n".join([*header, *(prefixes[row.change] + row.text for row in rows)]) + "\n"
