import hashlib
from collections import Counter, OrderedDict
from collections.abc import Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum

from rtool.storage.models import UnitSnapshot
from rtool.units.model import UnitKind

ROW_APPROVABLE_KINDS = frozenset({UnitKind.MODULE, UnitKind.FILE})
ROW_HASH_SEPARATOR = "\0"
DIFF_CACHE_SIZE = 16


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


_diff_cache: OrderedDict[tuple[int, int, str], tuple[DiffLine, ...]] = OrderedDict()


@dataclass(frozen=True)
class ChangedRow:
    side: Side
    index: int
    text: str
    row_hash: str


def is_binary(snapshot: UnitSnapshot) -> bool:
    return snapshot.kind == UnitKind.FILE and snapshot.base_text is None and snapshot.head_text is None


def side_lines(snapshot: UnitSnapshot, side: str) -> list[UnitLine]:
    if side == Side.BASE:
        return unit_lines(snapshot.base_text, snapshot.base_lines)
    return unit_lines(snapshot.head_text, snapshot.head_lines)


def unit_lines(text: str | None, line_numbers: Sequence[int | None]) -> list[UnitLine]:
    if text is None:
        return []
    lines = text.replace("\r\n", "\n").split("\n")
    if len(lines) > 1 and lines[-1] == "":
        lines.pop()
    numbers = list(line_numbers)
    return [UnitLine(line, numbers[index] if index < len(numbers) else None) for index, line in enumerate(lines)]


def diff_lines(old: Sequence[str], new: Sequence[str]) -> list[DiffLine]:
    key = _content_key(old, new)
    cached = _diff_cache.get(key)
    if cached is None:
        cached = _diff_cache[key] = _compute_diff_lines(old, new)
        while len(_diff_cache) > DIFF_CACHE_SIZE:
            _diff_cache.popitem(last=False)
    _diff_cache.move_to_end(key)
    return list(cached)


def _content_key(old: Sequence[str], new: Sequence[str]) -> tuple[int, int, str]:
    digest = hashlib.sha256()
    for line in (*old, ROW_HASH_SEPARATOR, *new):
        digest.update(line.encode())
        digest.update(b"\n")
    return len(old), len(new), digest.hexdigest()


def _compute_diff_lines(old: Sequence[str], new: Sequence[str]) -> tuple[DiffLine, ...]:
    matcher = SequenceMatcher(None, [line.rstrip() for line in old], [line.rstrip() for line in new], autojunk=False)
    result: list[DiffLine] = []
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if tag == "equal":
            result.extend(DiffLine(LineChange.CONTEXT, old_start + step, new_start + step, new[new_start + step]) for step in range(new_end - new_start))
            continue
        result.extend(DiffLine(LineChange.REMOVED, index, None, old[index]) for index in range(old_start, old_end))
        result.extend(DiffLine(LineChange.ADDED, None, index, new[index]) for index in range(new_start, new_end))
    return tuple(result)


def changed_rows(base: Sequence[str], head: Sequence[str], lines: Sequence[DiffLine] | None = None) -> list[ChangedRow]:
    occurrences: Counter[tuple[str, ...]] = Counter()
    rows: list[ChangedRow] = []
    for line in diff_lines(base, head) if lines is None else lines:
        if line.change == LineChange.ADDED and line.new_index is not None:
            side, index, texts = Side.HEAD, line.new_index, head
        elif line.change == LineChange.REMOVED and line.old_index is not None:
            side, index, texts = Side.BASE, line.old_index, base
        else:
            continue
        identity = (side.value, _clean(texts[index]), _neighbour(texts, index - 1), _neighbour(texts, index + 1))
        occurrence = occurrences[identity]
        occurrences[identity] += 1
        digest = hashlib.sha256(ROW_HASH_SEPARATOR.join((*identity, str(occurrence))).encode()).hexdigest()
        rows.append(ChangedRow(side, index, texts[index], digest))
    return rows


def _clean(line: str) -> str:
    return line.replace("\r", "").rstrip()


def _neighbour(lines: Sequence[str], index: int) -> str:
    return _clean(lines[index]) if 0 <= index < len(lines) else ""
