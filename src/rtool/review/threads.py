from dataclasses import dataclass

from rtool.errors import ForbiddenError, InvalidRequestError, NotFoundError
from rtool.review.anchoring import LINE_SEPARATOR, anchor_for, line_count, side_hash, side_text, surrounding
from rtool.review.context import ReviewContext
from rtool.review.keys import key_of
from rtool.review.rows import Side, side_lines
from rtool.review.thread_types import ThreadScope
from rtool.storage.models import Comment, Revision, Thread, ThreadAnchor, UnitSnapshot, utcnow

MAX_BODY_LENGTH = 65536


@dataclass(frozen=True)
class NewThread:
    scope: ThreadScope
    body: str
    snapshot: UnitSnapshot | None = None
    path: str | None = None
    side: Side = Side.HEAD
    line_offset: int | None = None
    line_count: int = 1


@dataclass(frozen=True)
class ThreadView:
    thread: Thread
    comments: list[Comment]
    anchor: ThreadAnchor | None
    unit_id: int | None
    file_line: int | None
    end_file_line: int | None = None

    @property
    def outdated(self) -> bool:
        return self.anchor is not None and self.anchor.outdated


def create_thread(context: ReviewContext, revision: Revision, request: NewThread) -> Thread:
    body = validated_body(request.body)
    thread = Thread(review_id=context.review.id, scope=request.scope.value, created_by=context.reviewer.id, created_revision_id=revision.id)
    if request.scope == ThreadScope.UNIT:
        _anchor_new_unit_thread(thread, request)
    elif request.scope == ThreadScope.FILE:
        if not request.path or all(snapshot.path != request.path for snapshot in context.store.reviews.snapshots(revision.id)):
            raise InvalidRequestError("File threads need the path of a changed file")
        thread.path = request.path
    context.store.threads.add_thread(thread)
    context.store.threads.add_comment(Comment(thread_id=thread.id, author_id=context.reviewer.id, body=body))
    if request.scope == ThreadScope.UNIT:
        context.store.threads.add_anchor(anchor_for(thread, revision.id))
    return thread


def add_comment(context: ReviewContext, thread: Thread, body: str) -> Comment:
    return context.store.threads.add_comment(Comment(thread_id=thread.id, author_id=context.reviewer.id, body=validated_body(body)))


def edit_comment(context: ReviewContext, comment: Comment, body: str) -> Comment:
    _check_author(context, comment)
    comment.body = validated_body(body)
    comment.edited_at = utcnow()
    return comment


def delete_comment(context: ReviewContext, comment: Comment) -> Comment:
    _check_author(context, comment)
    comment.deleted_at = comment.deleted_at or utcnow()
    return comment


def can_delete(context: ReviewContext, thread: Thread, comments: list[Comment]) -> bool:
    return thread.created_by == context.reviewer.id and all(comment.author_id == context.reviewer.id for comment in comments if comment.deleted_at is None)


def delete_thread(context: ReviewContext, thread: Thread) -> Thread:
    if thread.created_by != context.reviewer.id:
        raise ForbiddenError("You can only delete threads you started")
    if not can_delete(context, thread, context.store.threads.comments([thread.id])):
        raise ForbiddenError("Others replied to this thread, so it cannot be deleted. Resolve it instead.")
    thread.deleted_at = utcnow()
    return thread


def thread_views(context: ReviewContext, revision: Revision) -> list[ThreadView]:
    threads = [thread for thread in context.store.threads.threads(context.review.id) if thread.created_revision_id <= revision.id]
    ids = [thread.id for thread in threads]
    comments: dict[str, list[Comment]] = {}
    for comment in context.store.threads.comments(ids):
        comments.setdefault(comment.thread_id, []).append(comment)
    anchors: dict[str, ThreadAnchor] = {}
    for anchor in context.store.threads.anchors(ids):
        if anchor.revision_id <= revision.id:
            anchors[anchor.thread_id] = anchor
    snapshots = {key_of(snapshot): snapshot for snapshot in context.store.reviews.snapshots(revision.id, texts=False)}
    return [_view(thread, comments.get(thread.id, []), anchors.get(thread.id), revision, snapshots) for thread in threads]


def validated_body(body: str) -> str:
    text = body.strip()
    if not text or len(text) > MAX_BODY_LENGTH:
        raise InvalidRequestError(f"A comment needs between 1 and {MAX_BODY_LENGTH} characters")
    return text


def get_thread(context: ReviewContext, thread_id: str) -> Thread:
    thread = context.store.threads.get_thread(thread_id)
    if thread is None or thread.review_id != context.review.id:
        raise NotFoundError("Thread not found")
    return thread


def _view(
    thread: Thread, comments: list[Comment], anchor: ThreadAnchor | None, revision: Revision, snapshots: dict[tuple[str, str, str], UnitSnapshot]
) -> ThreadView:
    if anchor is None or anchor.outdated or anchor.revision_id != revision.id or anchor.line_offset is None:
        return ThreadView(thread, comments, anchor, None, None)
    snapshot = snapshots.get((anchor.path or "", anchor.kind or "", anchor.qualified_name or ""))
    if snapshot is None:
        return ThreadView(thread, comments, anchor, None, None)
    lines = side_lines(snapshot, thread.side or Side.HEAD)
    if anchor.line_offset >= len(lines):
        return ThreadView(thread, comments, anchor, snapshot.id, None)
    last = min(anchor.line_offset + line_count(thread) - 1, len(lines) - 1)
    return ThreadView(thread, comments, anchor, snapshot.id, lines[anchor.line_offset].file_line, lines[last].file_line)


def _anchor_new_unit_thread(thread: Thread, request: NewThread) -> None:
    snapshot = request.snapshot
    if snapshot is None or request.line_offset is None:
        raise InvalidRequestError("Unit threads need a unit and a line")
    anchor_to_unit(thread, snapshot, request.side, request.line_offset, request.line_count)


def anchor_to_unit(thread: Thread, snapshot: UnitSnapshot, side: Side, line_offset: int, count: int) -> None:
    lines = side_text(snapshot, side)
    last = line_offset + count - 1
    if count < 1 or not 0 <= line_offset <= last < len(lines):
        raise InvalidRequestError("The lines are outside the unit")
    before, after = surrounding(lines, line_offset, count)
    thread.path, thread.kind, thread.qualified_name = key_of(snapshot)
    thread.side = side.value
    thread.unit_hash = side_hash(snapshot, side)
    thread.line_offset = line_offset
    thread.line_text = LINE_SEPARATOR.join(line.rstrip() for line in lines[line_offset : last + 1])
    thread.context_before = [line.rstrip() for line in before]
    thread.context_after = [line.rstrip() for line in after]


def _check_author(context: ReviewContext, comment: Comment) -> None:
    if comment.author_id != context.reviewer.id:
        raise ForbiddenError("You can only change your own comments")
    if comment.deleted_at is not None:
        raise InvalidRequestError("The comment was deleted")
