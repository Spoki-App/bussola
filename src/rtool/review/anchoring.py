from collections.abc import Sequence
from dataclasses import dataclass

from rtool.review.keys import key_of
from rtool.review.rows import Side, side_lines
from rtool.review.thread_types import ThreadScope
from rtool.storage.models import Review, Revision, Thread, ThreadAnchor, UnitSnapshot
from rtool.storage.repositories import Store

CONTEXT_LINES = 3
LINE_SEPARATOR = "\n"


@dataclass(frozen=True)
class AnchorTarget:
    snapshot: UnitSnapshot
    line_offset: int


def side_text(snapshot: UnitSnapshot, side: str) -> list[str]:
    return [line.text for line in side_lines(snapshot, side)]


def side_hash(snapshot: UnitSnapshot, side: str) -> str | None:
    return snapshot.base_hash if side == Side.BASE else snapshot.head_hash


def surrounding(lines: Sequence[str], offset: int, line_count: int = 1) -> tuple[list[str], list[str]]:
    last = offset + line_count - 1
    return list(lines[max(0, offset - CONTEXT_LINES) : offset]), list(lines[last + 1 : last + 1 + CONTEXT_LINES])


def selected_lines(thread: Thread) -> list[str]:
    return (thread.line_text or "").split(LINE_SEPARATOR)


def line_count(thread: Thread) -> int:
    return len(selected_lines(thread))


def anchor_for(thread: Thread, revision_id: int) -> ThreadAnchor:
    return ThreadAnchor(thread.id, revision_id, thread.path, thread.kind, thread.qualified_name, thread.unit_hash, thread.line_offset)


def reanchor_threads(store: Store, review: Review, revision: Revision) -> None:
    threads = [thread for thread in store.threads.threads(review.id) if thread.scope == ThreadScope.UNIT]
    latest = {anchor.thread_id: anchor for anchor in store.threads.anchors([thread.id for thread in threads])} if threads else {}
    behind = [thread for thread in threads if thread.id not in latest or latest[thread.id].revision_id < revision.id]
    if not behind:
        return
    snapshots = store.reviews.snapshots(revision.id)
    for thread in behind:
        target = locate(thread, latest.get(thread.id), snapshots)
        if target is not None:
            thread.path, thread.kind, thread.qualified_name = key_of(target.snapshot)
        store.threads.add_anchor(_anchor(thread, revision.id, target))


def locate(thread: Thread, last: ThreadAnchor | None, snapshots: list[UnitSnapshot]) -> AnchorTarget | None:
    side = thread.side or Side.HEAD
    key = (thread.path, thread.kind, thread.qualified_name)
    last_hash = last.unit_hash if last else thread.unit_hash
    last_offset = last.line_offset if last and last.line_offset is not None else thread.line_offset or 0
    candidates = [snapshot for snapshot in snapshots if side_hash(snapshot, side) is not None]
    same_key = next((snapshot for snapshot in candidates if key_of(snapshot) == key), None)
    if same_key is not None and side_hash(same_key, side) == last_hash and last is not None and not last.outdated:
        return AnchorTarget(same_key, last_offset)
    if same_key is not None:
        return find_line(thread, [same_key], side, last_offset)
    moved = next((snapshot for snapshot in candidates if last_hash is not None and side_hash(snapshot, side) == last_hash), None)
    if moved is not None:
        return AnchorTarget(moved, last_offset)
    return find_line(thread, [snapshot for snapshot in candidates if snapshot.path == thread.path], side, last_offset)


def find_line(thread: Thread, snapshots: list[UnitSnapshot], side: str, previous_offset: int) -> AnchorTarget | None:
    wanted = selected_lines(thread)[0].strip()
    matches = [
        (snapshot, lines, index)
        for snapshot in snapshots
        for lines in [side_text(snapshot, side)]
        for index, line in enumerate(lines)
        if line.strip() == wanted
    ]
    if not matches:
        return None
    snapshot, _, offset = max(matches, key=lambda match: (_context_score(thread, match[1], match[2]), -abs(match[2] - previous_offset)))
    return AnchorTarget(snapshot, offset)


def _context_score(thread: Thread, lines: Sequence[str], index: int) -> int:
    before, after = surrounding(lines, index, line_count(thread))
    score = sum(1 for wanted, actual in zip(reversed(thread.context_before), reversed(before), strict=False) if wanted.strip() == actual.strip())
    return score + sum(1 for wanted, actual in zip(thread.context_after, after, strict=False) if wanted.strip() == actual.strip())


def _anchor(thread: Thread, revision_id: int, target: AnchorTarget | None) -> ThreadAnchor:
    if target is None:
        return ThreadAnchor(thread.id, revision_id, thread.path, thread.kind, thread.qualified_name, None, None, outdated=True)
    snapshot = target.snapshot
    side = thread.side or Side.HEAD
    return ThreadAnchor(thread.id, revision_id, snapshot.path, snapshot.kind, snapshot.qualified_name, side_hash(snapshot, side), target.line_offset)
