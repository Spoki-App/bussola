from dataclasses import dataclass, field
from datetime import datetime

from rtool.forge.base import Conversation, DiffSide, ForgeAdapter, RemoteNote, RemoteThread
from rtool.forge.publish import body_hash
from rtool.review.context import ReviewContext
from rtool.review.rows import Side, unit_lines
from rtool.review.threads import ThreadScope, ThreadStatus, anchor_to_unit
from rtool.storage.models import Comment, ForgeLink, PublishedComment, Revision, Thread, ThreadAnchor, UnitSnapshot, utcnow

GITHUB_EMAIL_DOMAIN = "users.noreply.github.com"
UNKNOWN_AUTHOR = "ghost"


@dataclass(frozen=True)
class UnitTarget:
    snapshot: UnitSnapshot
    side: Side
    line_offset: int
    count: int


def import_conversation(context: ReviewContext, adapter: ForgeAdapter, link: ForgeLink, revision: Revision) -> int:
    conversation = adapter.pull_request_conversation(link.repository, link.pr_number)
    importer = _Importer(context, adapter.provider, conversation, revision)
    for note in conversation.notes:
        importer.import_note(note)
    for remote in conversation.threads:
        importer.import_thread(remote)
    return importer.added


def find_unit_target(snapshots: list[UnitSnapshot], remote: RemoteThread) -> UnitTarget | None:
    if remote.line is None:
        return None
    side = Side.BASE if remote.side == DiffSide.LEFT else Side.HEAD
    first = remote.start_line or remote.line
    for snapshot in snapshots:
        if remote.path not in {snapshot.path, snapshot.old_path}:
            continue
        lines = unit_lines(snapshot.base_text, snapshot.base_lines) if side == Side.BASE else unit_lines(snapshot.head_text, snapshot.head_lines)
        numbers = [line.file_line for line in lines]
        if first in numbers and remote.line in numbers:
            start, end = numbers.index(first), numbers.index(remote.line)
            if end >= start:
                return UnitTarget(snapshot, side, start, end - start + 1)
    return None


@dataclass
class _Importer:
    context: ReviewContext
    provider: str
    conversation: Conversation
    revision: Revision
    added: int = 0
    _known: dict[str, PublishedComment] = field(default_factory=dict)
    _snapshots: list[UnitSnapshot] | None = None

    def __post_init__(self) -> None:
        notes = self.conversation.notes + [note for thread in self.conversation.threads for note in thread.comments]
        self._known = self.context.store.forge.published_by_remote(self.provider, [note.remote_id for note in notes])

    def import_note(self, note: RemoteNote) -> None:
        if note.remote_id in self._known:
            return
        thread = self._add_thread(self._thread(note, ThreadScope.REVIEW, None))
        self._add_comment(thread, note)

    def import_thread(self, remote: RemoteThread) -> None:
        if not remote.comments:
            return
        known = next((self._known[note.remote_id] for note in remote.comments if note.remote_id in self._known), None)
        thread = self._existing_thread(known) if known else self._new_thread(remote)
        if thread is None:
            return
        thread.status = (ThreadStatus.RESOLVED if remote.resolved else ThreadStatus.OPEN).value
        for note in remote.comments:
            if note.remote_id not in self._known:
                self._add_comment(thread, note)

    def _existing_thread(self, record: PublishedComment) -> Thread | None:
        comment = self.context.store.threads.get_comment(record.comment_id)
        return self.context.store.threads.get_thread(comment.thread_id) if comment else None

    def _new_thread(self, remote: RemoteThread) -> Thread:
        thread = self._thread(remote.comments[0], ThreadScope.FILE, remote.path)
        target = find_unit_target(self._unit_snapshots(), remote) if self.conversation.head_sha == self.revision.head_sha else None
        if target is not None:
            thread.scope = ThreadScope.UNIT.value
            anchor_to_unit(thread, target.snapshot, target.side, target.line_offset, target.count)
        self._add_thread(thread)
        if target is not None:
            anchor = ThreadAnchor(thread.id, self.revision.id, thread.path, thread.kind, thread.qualified_name, thread.unit_hash, thread.line_offset)
            self.context.store.threads.add_anchor(anchor)
        return thread

    def _thread(self, first: RemoteNote, scope: ThreadScope, path: str | None) -> Thread:
        return Thread(
            review_id=self.context.review.id,
            scope=scope.value,
            created_by=self._author_id(first.author),
            created_revision_id=self.revision.id,
            path=path,
            created_at=_parse_time(first.created_at),
        )

    def _add_thread(self, thread: Thread) -> Thread:
        return self.context.store.threads.add_thread(thread)

    def _add_comment(self, thread: Thread, note: RemoteNote) -> None:
        comment = self.context.store.threads.add_comment(
            Comment(thread_id=thread.id, author_id=self._author_id(note.author), body=note.body, created_at=_parse_time(note.created_at))
        )
        record = PublishedComment(comment.id, self.provider, note.remote_id, note.url or None, body_hash(self.context, comment))
        self._known[note.remote_id] = self.context.store.forge.save_published(record)
        self.added += 1

    def _author_id(self, login: str) -> int:
        if login and login == self.conversation.viewer:
            return self.context.reviewer.id
        name = login or UNKNOWN_AUTHOR
        return self.context.store.reviews.reviewer(f"{name}@{GITHUB_EMAIL_DOMAIN}", name).id

    def _unit_snapshots(self) -> list[UnitSnapshot]:
        if self._snapshots is None:
            self._snapshots = self.context.store.reviews.snapshots(self.revision.id)
        return self._snapshots


def _parse_time(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return utcnow()
