from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import groupby

from bussola.review.rows import LineChange, Side, UnitLine, diff_lines, side_lines
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
    end: int

    @property
    def count(self) -> int:
        return self.end - self.start + 1

    def lines(self) -> list[UnitLine]:
        return side_lines(self.snapshot, self.side)[self.start : self.end + 1]


@dataclass(frozen=True)
class Move:
    removed: CodeRange
    added: CodeRange
    similarity: float
    identical: bool


@dataclass(frozen=True)
class _Block:
    snapshot: UnitSnapshot
    side: Side
    hunk: int
    offsets: list[int]
    texts: list[str]
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
        for block in _blocks(snapshot):
            (removed if block.side == Side.BASE else added).append(block)
    candidates = [move for block in removed for move in _matches(block, added)]
    candidates.sort(key=lambda move: (-min(move.removed.count, move.added.count), -move.similarity))
    claimed: set[tuple[int, Side, int]] = set()
    moves: list[Move] = []
    for move in candidates:
        lines = {*_claims(move.removed), *_claims(move.added)}
        if claimed.isdisjoint(lines):
            claimed |= lines
            moves.append(move)
    return sorted(moves, key=lambda move: (move.removed.snapshot.path, move.removed.snapshot.id, move.removed.start))


def same_code(old: Sequence[UnitLine], new: Sequence[UnitLine]) -> bool:
    return _stripped(old) == _stripped(new)


def _stripped(lines: Sequence[UnitLine]) -> list[str]:
    return [line.text.strip() for line in lines if line.text.strip()]


def _claims(code: CodeRange) -> Iterator[tuple[int, Side, int]]:
    return ((code.snapshot.id, code.side, offset) for offset in range(code.start, code.end + 1))


def _blocks(snapshot: UnitSnapshot) -> Iterator[_Block]:
    old = side_lines(snapshot, Side.BASE)
    new = side_lines(snapshot, Side.HEAD)
    lines = diff_lines([line.text for line in old], [line.text for line in new])
    changed_runs = (list(run) for changed, run in groupby(lines, key=lambda line: line.change != LineChange.CONTEXT) if changed)
    for hunk, run in enumerate(changed_runs):
        removed = [line.old_index for line in run if line.change == LineChange.REMOVED and line.old_index is not None]
        added = [line.new_index for line in run if line.change == LineChange.ADDED and line.new_index is not None]
        yield from _block(snapshot, Side.BASE, hunk, removed, old)
        yield from _block(snapshot, Side.HEAD, hunk, added, new)


def _block(snapshot: UnitSnapshot, side: Side, hunk: int, offsets: list[int], lines: list[UnitLine]) -> Iterator[_Block]:
    kept = [offset for offset in offsets if _is_code(lines[offset].text)]
    texts = [lines[offset].text.strip() for offset in kept]
    if sum(1 for text in texts if _is_significant(text)) >= MIN_MATCHED_LINES:
        yield _Block(snapshot, side, hunk, kept, texts, ["".join(text.split()) for text in texts])


def _is_code(text: str) -> bool:
    stripped = text.strip()
    return bool(stripped) and stripped != UNIT_PLACEHOLDER


def _is_significant(text: str) -> bool:
    return sum(1 for character in text if character.isalnum() or character == "_") >= MIN_SIGNIFICANT_WORD_CHARACTERS


def _matches(removed: _Block, added: list[_Block]) -> Iterator[Move]:
    for block in _candidates(removed, added):
        if block.snapshot.id == removed.snapshot.id and block.hunk == removed.hunk:
            continue
        move = _compare(removed, block)
        if move is not None:
            yield move


def _candidates(removed: _Block, added: list[_Block]) -> list[_Block]:
    wanted = {text for text in removed.compact if _is_significant(text)}
    return [block for block in added if not wanted.isdisjoint(block.compact)]


def _compare(removed: _Block, added: _Block) -> Move | None:
    pairs = _pairs(removed.compact, added.compact)
    if not pairs:
        return None
    first, last = pairs[0], pairs[-1]
    shared = sum(pair.ratio * (len(removed.compact[pair.removed]) + len(added.compact[pair.added])) for pair in pairs)
    total = sum(map(len, removed.compact[first.removed : last.removed + 1])) + sum(map(len, added.compact[first.added : last.added + 1]))
    similarity = shared / total
    significant = sum(1 for pair in pairs if _is_significant(removed.texts[pair.removed]))
    matched = sum(len(removed.compact[pair.removed]) for pair in pairs)
    if similarity < MIN_SIMILARITY or significant < MIN_MATCHED_LINES or matched < MIN_MATCHED_CHARACTERS:
        return None
    identical = removed.texts[first.removed : last.removed + 1] == added.texts[first.added : last.added + 1]
    return Move(
        CodeRange(removed.snapshot, Side.BASE, removed.offsets[first.removed], removed.offsets[last.removed]),
        CodeRange(added.snapshot, Side.HEAD, added.offsets[first.added], added.offsets[last.added]),
        round(similarity, 3),
        identical,
    )


def _pairs(old: list[str], new: list[str]) -> list[_Pair]:
    pairs: list[_Pair] = []
    for tag, old_start, old_end, new_start, new_end in SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        if tag == "equal":
            pairs.extend(_Pair(index, new_start + step, 1.0) for step, index in enumerate(range(old_start, old_end)))
        elif tag == "replace":
            for index, other in zip(range(old_start, old_end), range(new_start, new_end), strict=False):
                ratio = SequenceMatcher(None, old[index], new[other], autojunk=False).ratio()
                if ratio >= MIN_LINE_SIMILARITY:
                    pairs.append(_Pair(index, other, ratio))
    return pairs
