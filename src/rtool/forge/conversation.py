import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from rtool.forge.base import Conversation, DiffSide, ForgeAdapter, RemoteNote, RemoteThread
from rtool.forge.publish import body_hash
from rtool.review.anchoring import anchor_for
from rtool.review.context import ReviewContext
from rtool.review.rows import Side, side_lines
from rtool.review.thread_types import ThreadScope, ThreadStatus
from rtool.review.threads import anchor_to_unit
from rtool.storage.models import Comment, ForgeLink, PublishedComment, Revision, Thread, UnitSnapshot, utcnow

GITHUB_EMAIL_DOMAIN = "users.noreply.github.com"
UNKNOWN_AUTHOR = "ghost"


@dataclass(frozen=True)
class UnitTarget:
    snapshot: UnitSnapshot
    side: Side
    line_offset: int
    count: int


def import_conversation(context: ReviewContext, adapter: ForgeAdapter, link: ForgeLink, revision: Revision, conversation: Conversation | None = None) -> int:
    conversation = conversation or adapter.pull_request_conversation(link.repository, link.pr_number)
    importer = _Importer(context, adapter.provider, conversation, revision)
    for note in conversation.notes:
        importer.import_note(note)
    for remote in conversation.threads:
        importer.import_thread(remote)
    return importer.changes


def push_resolution(context: ReviewContext, adapter: ForgeAdapter, thread: Thread, resolved: bool) -> None:
    link = context.store.forge.link(context.review.id)
    if link is None:
        return
    comment_ids = [comment.id for comment in context.store.threads.comments([thread.id])]
    remote_ids = {record.remote_id for record in context.store.forge.published(comment_ids).values() if adapter.can_reply(record.remote_id)}
    if not remote_ids:
        return
    conversation = adapter.pull_request_conversation(link.repository, link.pr_number)
    remote = next((item for item in conversation.threads if any(note.remote_id in remote_ids for note in item.comments)), None)
    if remote is not None and remote.remote_id and remote.resolved != resolved:
        adapter.set_thread_resolved(remote.remote_id, resolved)


def find_unit_target(snapshots: list[UnitSnapshot], remote: RemoteThread) -> UnitTarget | None:
    if remote.line is None:
        return None
    side = Side.BASE if remote.side == DiffSide.LEFT else Side.HEAD
    first = remote.start_line or remote.line
    for snapshot in snapshots:
        if remote.path not in {snapshot.path, snapshot.old_path}:
            continue
        lines = side_lines(snapshot, side)
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
    changes: int = 0
    _known: dict[str, list[PublishedComment]] = field(default_factory=dict)
    _snapshots: list[UnitSnapshot] | None = None

    def __post_init__(self) -> None:
        notes = self.conversation.notes + [note for thread in self.conversation.threads for note in thread.comments]
        known: defaultdict[str, list[PublishedComment]] = defaultdict(list)
        for record in self.context.store.forge.published_by_remote(self.provider, [note.remote_id for note in notes]):
            if record.remote_id is not None:
                known[record.remote_id].append(record)
        self._known = dict(known)

    def import_note(self, note: RemoteNote) -> None:
        if note.remote_id in self._known:
            self._follow_edit(note)
            return
        thread = self.context.store.threads.add_thread(self._thread(note, ThreadScope.REVIEW, None))
        self._add_comment(thread, note)

    def import_thread(self, remote: RemoteThread) -> None:
        if not remote.comments:
            return
        known = next((self._known[note.remote_id][0] for note in remote.comments if note.remote_id in self._known), None)
        thread = self._existing_thread(known) if known else self._new_thread(remote)
        if thread is None:
            return
        if thread.scope == ThreadScope.FILE and self._place(thread, remote):
            self.changes += 1
        status = (ThreadStatus.RESOLVED if remote.resolved else ThreadStatus.OPEN).value
        if thread.status != status:
            thread.status = status
            self.changes += 1
        for note in remote.comments:
            if note.remote_id in self._known:
                self._follow_edit(note)
            else:
                self._add_comment(thread, note)

    def _follow_edit(self, note: RemoteNote) -> None:
        records = self._known[note.remote_id]
        if len(records) != 1:
            return
        record, remote_hash = records[0], _text_hash(note.body)
        previous, record.remote_body_hash = record.remote_body_hash, remote_hash
        if previous is None or previous == remote_hash:
            return
        comment = self.context.store.threads.get_comment(record.comment_id)
        if comment is None or comment.deleted_at is not None or record.published_body_hash != body_hash(self.context, comment):
            return
        comment.body, comment.edited_at = note.body, utcnow()
        record.published_body_hash = body_hash(self.context, comment)
        self.changes += 1

    def _existing_thread(self, record: PublishedComment) -> Thread | None:
        comment = self.context.store.threads.get_comment(record.comment_id)
        return self.context.store.threads.get_thread(comment.thread_id) if comment else None

    def _new_thread(self, remote: RemoteThread) -> Thread:
        thread = self.context.store.threads.add_thread(self._thread(remote.comments[0], ThreadScope.FILE, remote.path))
        self._place(thread, remote)
        return thread

    def _place(self, thread: Thread, remote: RemoteThread) -> bool:
        if remote.line is None or self.conversation.pull.head_sha != self.revision.head_sha:
            return False
        target = find_unit_target(self._unit_snapshots(), remote)
        if target is None:
            return False
        thread.scope = ThreadScope.UNIT.value
        anchor_to_unit(thread, target.snapshot, target.side, target.line_offset, target.count)
        self.context.store.threads.add_anchor(anchor_for(thread, self.revision.id))
        return True

    def _thread(self, first: RemoteNote, scope: ThreadScope, path: str | None) -> Thread:
        return Thread(
            review_id=self.context.review.id,
            scope=scope.value,
            created_by=self._author_id(first.author),
            created_revision_id=self.revision.id,
            path=path,
            created_at=_parse_time(first.created_at),
        )

    def _add_comment(self, thread: Thread, note: RemoteNote) -> None:
        comment = self.context.store.threads.add_comment(
            Comment(thread_id=thread.id, author_id=self._author_id(note.author), body=note.body, created_at=_parse_time(note.created_at))
        )
        record = PublishedComment(comment.id, self.provider, note.remote_id, note.url or None, body_hash(self.context, comment))
        record.remote_body_hash = _text_hash(note.body)
        self._known[note.remote_id] = [self.context.store.forge.save_published(record)]
        self.changes += 1

    def _author_id(self, login: str) -> int:
        if login and login == self.conversation.viewer:
            return self.context.reviewer.id
        name = login or UNKNOWN_AUTHOR
        return self.context.store.reviews.reviewer(f"{name}@{GITHUB_EMAIL_DOMAIN}", name).id

    def _unit_snapshots(self) -> list[UnitSnapshot]:
        if self._snapshots is None:
            self._snapshots = self.context.store.reviews.snapshots(self.revision.id)
        return self._snapshots


def _text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _parse_time(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return utcnow()
