from collections import defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import groupby

from bussola.review.rows import LineChange, Side, UnitLine, compute_diff_lines, side_lines, without_spaces
from bussola.storage.models import UnitSnapshot
from bussola.units.normalize import UNIT_PLACEHOLDER

MIN_SIMILARITY = 0.8
MIN_LINE_SIMILARITY = 0.6
MIN_MATCHED_LINES = 3
MIN_MATCHED_CHARACTERS = 60
MIN_SIGNIFICANT_WORD_CHARACTERS = 4


@dataclass(frozen=True)
class CodeRange:
    snapshot: UnitSnapshot
    side: Side
    start: int
    lines: Sequence[UnitLine]

    @property
    def stop(self) -> int:
        return self.start + len(self.lines)


@dataclass(frozen=True)
class Move:
    removed: CodeRange
    added: CodeRange
    similarity: float
    identical: bool


@dataclass(frozen=True)
class _Block:
    snapshot: UnitSnapshot
    hunk: int
    lines: list[UnitLine]
    offsets: list[int]
    compact: list[str]


@dataclass(frozen=True)
class _Pair:
    removed: int
    added: int
    ratio: float


def detect_moves(snapshots: Sequence[UnitSnapshot]) -> list[Move]:
    removed: list[_Block] = []
    added: list[_Block] = []
    for snapshot in snapshots:
        removed_blocks, added_blocks = _blocks(snapshot)
        removed += removed_blocks
        added += added_blocks
    index: defaultdict[str, list[_Block]] = defaultdict(list)
    for block in added:
        for text in {text for text in block.compact if _is_significant(text)}:
            index[text].append(block)
    candidates = [move for block in removed for move in _matches(block, index)]
    candidates.sort(key=lambda move: (-min(len(move.removed.lines), len(move.added.lines)), -move.similarity))
    claimed: set[tuple[int, Side, int]] = set()
    moves: list[Move] = []
    for move in candidates:
        lines = {*_claims(move.removed), *_claims(move.added)}
        if claimed.isdisjoint(lines):
            claimed |= lines
            moves.append(move)
    return sorted(moves, key=lambda move: (move.removed.snapshot.path, move.removed.snapshot.id, move.removed.start))


def same_code(old: Sequence[UnitLine], new: Sequence[UnitLine]) -> bool:
    return _code_texts(old) == _code_texts(new)


def _code_texts(lines: Sequence[UnitLine]) -> list[str]:
    return [line.text.strip() for line in lines if _is_code(line.text)]


def _claims(code: CodeRange) -> Iterator[tuple[int, Side, int]]:
    return ((code.snapshot.id, code.side, offset) for offset in range(code.start, code.stop))


def _blocks(snapshot: UnitSnapshot) -> tuple[list[_Block], list[_Block]]:
    old = side_lines(snapshot, Side.BASE)
    new = side_lines(snapshot, Side.HEAD)
    lines = compute_diff_lines([line.text for line in old], [line.text for line in new])
    changed_runs = (list(run) for changed, run in groupby(lines, key=lambda line: line.change != LineChange.CONTEXT) if changed)
    removed: list[_Block] = []
    added: list[_Block] = []
    for hunk, run in enumerate(changed_runs):
        removed += _block(snapshot, hunk, [line.old_index for line in run if line.change == LineChange.REMOVED and line.old_index is not None], old)
        added += _block(snapshot, hunk, [line.new_index for line in run if line.change == LineChange.ADDED and line.new_index is not None], new)
    return removed, added


def _block(snapshot: UnitSnapshot, hunk: int, offsets: list[int], lines: list[UnitLine]) -> list[_Block]:
    kept = [offset for offset in offsets if _is_code(lines[offset].text)]
    compact = [without_spaces(lines[offset].text) for offset in kept]
    if sum(1 for text in compact if _is_significant(text)) < MIN_MATCHED_LINES:
        return []
    return [_Block(snapshot, hunk, lines, kept, compact)]


def _is_code(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and stripped != UNIT_PLACEHOLDER


def _is_significant(text: str) -> bool:
    return sum(1 for character in text if character.isalnum() or character == "_") >= MIN_SIGNIFICANT_WORD_CHARACTERS


def _matches(removed: _Block, index: dict[str, list[_Block]]) -> Iterator[Move]:
    candidates = {id(block): block for text in removed.compact for block in index.get(text, [])}
    for block in candidates.values():
        if block.snapshot.id == removed.snapshot.id and block.hunk == removed.hunk:
            continue
        move = _compare(removed, block)
        if move is not None:
            yield move


def _compare(removed: _Block, added: _Block) -> Move | None:
    pairs = _pairs(removed.compact, added.compact)
    if not pairs:
        return None
    first, last = pairs[0], pairs[-1]
    shared = sum(pair.ratio * (len(removed.compact[pair.removed]) + len(added.compact[pair.added])) for pair in pairs)
    total = sum(map(len, removed.compact[first.removed : last.removed + 1])) + sum(map(len, added.compact[first.added : last.added + 1]))
    similarity = shared / total
    significant = sum(1 for pair in pairs if _is_significant(removed.compact[pair.removed]))
    matched = sum(len(removed.compact[pair.removed]) for pair in pairs)
    if similarity < MIN_SIMILARITY or significant < MIN_MATCHED_LINES or matched < MIN_MATCHED_CHARACTERS:
        return None
    old = _range(removed, Side.BASE, first.removed, last.removed)
    new = _range(added, Side.HEAD, first.added, last.added)
    return Move(old, new, round(similarity, 3), same_code(old.lines, new.lines))


def _range(block: _Block, side: Side, first: int, last: int) -> CodeRange:
    start, stop = block.offsets[first], block.offsets[last] + 1
    return CodeRange(block.snapshot, side, start, block.lines[start:stop])


def _pairs(old: list[str], new: list[str]) -> list[_Pair]:
    pairs: list[_Pair] = []
    for tag, old_start, old_end, new_start, new_end in SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag == "equal":
            pairs.extend(_Pair(index, new_start + step, 1.0) for step, index in enumerate(range(old_start, old_end)))
        elif tag == "replace":
            for index, other in zip(range(old_start, old_end), range(new_start, new_end), strict=False):
                ratio = _line_ratio(old[index], new[other])
                if ratio >= MIN_LINE_SIMILARITY:
                    pairs.append(_Pair(index, other, ratio))
    return pairs


def _line_ratio(old: str, new: str) -> float:
    matcher = SequenceMatcher(None, old, new, autojunk=False)
    if matcher.real_quick_ratio() < MIN_LINE_SIMILARITY or matcher.quick_ratio() < MIN_LINE_SIMILARITY:
        return 0.0
    return matcher.ratio()
