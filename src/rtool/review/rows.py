import hashlib
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum

from rtool.units.model import UnitKind

ROW_APPROVABLE_KINDS = frozenset({UnitKind.MODULE, UnitKind.FILE})
ROW_HASH_SEPARATOR = "\0"


class Side(StrEnum):
    HEAD = "head"
    BASE = "base"


class LineChange(StrEnum):
    CONTEXT = "context"
    ADDED = "added"
    REMOVED = "removed"


@dataclass(frozen=True)
class UnitLine:
    text: str
    file_line: int | None


@dataclass(frozen=True)
class DiffLine:
    change: LineChange
    old_index: int | None
    new_index: int | None
    text: str


@dataclass(frozen=True)
class ChangedRow:
    side: Side
    index: int
    text: str
    row_hash: str


def unit_lines(text: str | None, line_numbers: Sequence[int | None]) -> list[UnitLine]:
    if text is None:
        return []
    lines = text.replace("\r\n", "\n").split("\n")
    if len(lines) > 1 and lines[-1] == "":
        lines.pop()
    numbers = list(line_numbers)
    return [UnitLine(line, numbers[index] if index < len(numbers) else None) for index, line in enumerate(lines)]


def diff_lines(old: Sequence[str], new: Sequence[str]) -> list[DiffLine]:
    matcher = SequenceMatcher(None, [line.rstrip() for line in old], [line.rstrip() for line in new], autojunk=False)
    result: list[DiffLine] = []
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if tag == "equal":
            result.extend(DiffLine(LineChange.CONTEXT, old_start + step, new_start + step, new[new_start + step]) for step in range(new_end - new_start))
            continue
        result.extend(DiffLine(LineChange.REMOVED, index, None, old[index]) for index in range(old_start, old_end))
        result.extend(DiffLine(LineChange.ADDED, None, index, new[index]) for index in range(new_start, new_end))
    return result


def changed_rows(base: Sequence[str], head: Sequence[str]) -> list[ChangedRow]:
    occurrences: Counter[tuple[str, ...]] = Counter()
    rows: list[ChangedRow] = []
    for line in diff_lines(base, head):
        if line.change == LineChange.ADDED and line.new_index is not None:
            side, index, lines = Side.HEAD, line.new_index, head
        elif line.change == LineChange.REMOVED and line.old_index is not None:
            side, index, lines = Side.BASE, line.old_index, base
        else:
            continue
        identity = (side.value, _clean(lines[index]), _neighbour(lines, index - 1), _neighbour(lines, index + 1))
        occurrence = occurrences[identity]
        occurrences[identity] += 1
        digest = hashlib.sha256(ROW_HASH_SEPARATOR.join((*identity, str(occurrence))).encode()).hexdigest()
        rows.append(ChangedRow(side, index, lines[index], digest))
    return rows


def _clean(line: str) -> str:
    return line.replace("\r", "").rstrip()


def _neighbour(lines: Sequence[str], index: int) -> str:
    return _clean(lines[index]) if 0 <= index < len(lines) else ""
