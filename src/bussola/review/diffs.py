from collections.abc import Sequence
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
    REVIEWED = "reviewed"


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
class EarlierVersion:
    mode: DiffMode
    head_hash: str | None
    lines: list[UnitLine] | None


@dataclass(frozen=True)
class DiffChoice:
    effective: DiffMode
    available: list[DiffMode]
    approved_text_unavailable: bool
    earlier_lines: list[UnitLine] | None = None


def approved_version(approval: Approval) -> EarlierVersion:
    text = approval.approved_text
    lines = None if text is None else [UnitLine(line.text, index + 1) for index, line in enumerate(unit_lines(text, []))]
    return EarlierVersion(DiffMode.APPROVED, approval.head_hash, lines)


def reviewed_version(reviewed: UnitSnapshot) -> EarlierVersion:
    return EarlierVersion(DiffMode.REVIEWED, reviewed.head_hash, side_lines(reviewed, Side.HEAD))


def choose_diff_mode(snapshot: UnitSnapshot, earlier: EarlierVersion | None, requested: DiffMode | None, *, prefer_base: bool = False) -> DiffChoice:
    if earlier is None or earlier.head_hash == snapshot.head_hash:
        return DiffChoice(DiffMode.BASE, [DiffMode.BASE], approved_text_unavailable=False)
    has_lines = earlier.lines is not None
    if requested is None:
        wanted = earlier.mode if has_lines and not prefer_base else DiffMode.BASE
    else:
        wanted = DiffMode.BASE if requested == DiffMode.BASE else earlier.mode
    available = [DiffMode.BASE, earlier.mode]
    if wanted == earlier.mode and has_lines:
        return DiffChoice(earlier.mode, available, approved_text_unavailable=False, earlier_lines=earlier.lines)
    return DiffChoice(DiffMode.BASE, available, approved_text_unavailable=wanted == earlier.mode)


def build_diff(snapshot: UnitSnapshot, choice: DiffChoice) -> UnitDiff:
    new = side_lines(snapshot, Side.HEAD)
    old = side_lines(snapshot, Side.BASE) if choice.earlier_lines is None else choice.earlier_lines
    with_hashes = choice.earlier_lines is None and UnitKind(snapshot.kind) in ROW_APPROVABLE_KINDS
    rows, unified = compare_lines(old, new, snapshot.old_path or snapshot.path, snapshot.path, with_hashes=with_hashes)
    return UnitDiff(choice.effective, rows, unified, is_binary(snapshot))


def compare_lines(old: Sequence[UnitLine], new: Sequence[UnitLine], old_path: str, new_path: str, *, with_hashes: bool = False) -> tuple[list[DiffRow], str]:
    rows = [_labelled(row) for row in _rows(old, new, with_hashes=with_hashes)]
    return rows, _unified(old_path, new_path, rows)


def _labelled(row: DiffRow) -> DiffRow:
    if row.text != UNIT_PLACEHOLDER:
        return row
    return DiffRow(row.change, row.old_index, row.new_index, row.old_line, row.new_line, PLACEHOLDER_LABEL, row.row_hash, placeholder=True)


def _rows(old: Sequence[UnitLine], new: Sequence[UnitLine], *, with_hashes: bool) -> list[DiffRow]:
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
