import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from rtool.errors import ConflictError
from rtool.forge.base import DiffSide, ForgeAdapter, ForgeError, InlineComment, LineRanges, RemoteComment, ReviewSubmission
from rtool.review.context import ReviewContext
from rtool.review.rows import Side
from rtool.review.thread_types import ThreadScope
from rtool.review.threads import ThreadView, thread_views
from rtool.storage.models import Comment, ForgeLink, PublishedComment, Revision

GROUP_SEPARATOR = "\n\n---\n\n"
SHORT_SHA = 8


class PublishStatus(StrEnum):
    PUBLISHED = "published"
    UPDATED = "updated"
    SKIPPED = "skipped"
    FAILED = "failed"


@dataclass(frozen=True)
class Outcome:
    comment_ids: tuple[str, ...]
    status: PublishStatus
    detail: str
    url: str | None = None


@dataclass(frozen=True)
class PublishResult:
    review_url: str | None
    outcomes: list[Outcome]


@dataclass
class PublishPlan:
    inline: list[tuple[list[Comment], InlineComment]] = field(default_factory=list)
    files: list[tuple[list[Comment], str, str]] = field(default_factory=list)
    body_parts: list[tuple[list[Comment], str]] = field(default_factory=list)
    replies: list[tuple[Comment, str, str]] = field(default_factory=list)
    updates: list[tuple[list[Comment], str, str]] = field(default_factory=list)
    skipped: list[Outcome] = field(default_factory=list)


def publish_comments(context: ReviewContext, adapter: ForgeAdapter, revision: Revision, *, draft: bool) -> PublishResult:
    link = require_link(context)
    pull = adapter.pull_request(link.repository, link.pr_number)
    if pull.head_sha != revision.head_sha:
        pr_head, reviewed = pull.head_sha[:SHORT_SHA], revision.head_sha[:SHORT_SHA]
        raise ConflictError(f"The pull request head ({pr_head}) differs from the reviewed head ({reviewed}). Push the branch or refresh the review first.")
    plan = build_plan(context, revision, adapter.diff_ranges(link.repository, link.pr_number))
    publisher = _Publisher(context, adapter, link, revision.head_sha, list(plan.skipped))
    review_url = publisher.submit_review(plan, draft=draft)
    for comments, path, body in plan.files:
        publisher.attempt(comments, lambda path=path, body=body: adapter.create_file_comment(link.repository, link.pr_number, revision.head_sha, path, body))
    for comment, remote_id, body in plan.replies:
        publisher.attempt([comment], lambda remote_id=remote_id, body=body: adapter.reply(link.repository, link.pr_number, remote_id, body))
    for comments, remote_id, body in plan.updates:
        publisher.update(comments, remote_id, body)
    return PublishResult(review_url, publisher.outcomes)


def require_link(context: ReviewContext) -> ForgeLink:
    link = context.store.forge.link(context.review.id)
    if link is None:
        raise ConflictError("Link this review to a pull request first")
    return link


def build_plan(context: ReviewContext, revision: Revision, ranges: dict[str, LineRanges]) -> PublishPlan:
    plan = PublishPlan()
    views = thread_views(context, revision)
    published = context.store.forge.published([comment.id for view in views for comment in view.comments])
    for view in views:
        comments = [comment for comment in view.comments if comment.deleted_at is None]
        records = [published[comment.id] for comment in comments if comment.id in published]
        if not comments:
            continue
        if not records:
            _plan_new_thread(context, view, comments, ranges, plan)
            continue
        _plan_existing_thread(context, view, comments, published, plan)
    return plan


def pending_comment_count(context: ReviewContext, revision: Revision) -> int:
    views = thread_views(context, revision)
    comments = [comment for view in views for comment in view.comments if comment.deleted_at is None]
    published = context.store.forge.published([comment.id for comment in comments])
    return sum(1 for comment in comments if comment.id not in published or _is_edited(context, comment, published[comment.id]))


def render_comment(context: ReviewContext, comment: Comment) -> str:
    if comment.author_id == context.reviewer.id:
        return comment.body
    author = context.store.reviews.get_reviewer(comment.author_id)
    return f"**{author.name if author else 'Someone'}:** {comment.body}"


def _plan_new_thread(context: ReviewContext, view: ThreadView, comments: list[Comment], ranges: dict[str, LineRanges], plan: PublishPlan) -> None:
    thread = view.thread
    body = GROUP_SEPARATOR.join(render_comment(context, comment) for comment in comments)
    if thread.scope == ThreadScope.REVIEW:
        plan.body_parts.append((comments, body))
        return
    path = thread.path or ""
    if thread.scope == ThreadScope.UNIT:
        side = DiffSide.LEFT if thread.side == Side.BASE else DiffSide.RIGHT
        start, end = view.file_line, view.end_file_line or view.file_line
        if start is not None and end is not None and not view.outdated and path in ranges and ranges[path].contains(side, start, end):
            plan.inline.append((comments, InlineComment(path, end, side, body, start_line=start)))
            return
        body = f"{_unit_location(view)}{body}"
    if path in ranges:
        plan.files.append((comments, path, body))
    else:
        plan.body_parts.append((comments, f"On `{path}`:\n\n{body}"))


def _plan_existing_thread(context: ReviewContext, view: ThreadView, comments: list[Comment], published: dict[str, PublishedComment], plan: PublishPlan) -> None:
    thread_remote = next((record.remote_id for comment in comments if (record := published.get(comment.id)) and is_comment_id(record.remote_id)), None)
    for comment in comments:
        if comment.id in published:
            continue
        if thread_remote is not None:
            plan.replies.append((comment, thread_remote, render_comment(context, comment)))
        else:
            root = comments[0].body.splitlines()[0] if comments[0].body else ""
            plan.body_parts.append(([comment], f"> {root}\n\n{render_comment(context, comment)}"))
    groups: dict[str, list[Comment]] = {}
    for comment in comments:
        record = published.get(comment.id)
        if record is not None and record.remote_id is not None and is_comment_id(record.remote_id):
            groups.setdefault(record.remote_id, []).append(comment)
    for remote_id, members in groups.items():
        if any(_is_edited(context, member, published[member.id]) for member in members):
            plan.updates.append((members, remote_id, GROUP_SEPARATOR.join(render_comment(context, member) for member in members)))
    edited_in_body = [comment for comment in comments if comment.id in published and not is_comment_id(published[comment.id].remote_id)]
    edited_in_body = [comment for comment in edited_in_body if _is_edited(context, comment, published[comment.id])]
    if edited_in_body and view.thread.scope == ThreadScope.REVIEW:
        detail = "Edits to comments sent in a review body cannot be updated on GitHub"
        plan.skipped.append(Outcome(tuple(comment.id for comment in edited_in_body), PublishStatus.SKIPPED, detail))


@dataclass
class _Publisher:
    context: ReviewContext
    adapter: ForgeAdapter
    link: ForgeLink
    commit_id: str
    outcomes: list[Outcome]

    def submit_review(self, plan: PublishPlan, *, draft: bool) -> str | None:
        if not plan.inline and not plan.body_parts:
            return None
        body = GROUP_SEPARATOR.join(text for _, text in plan.body_parts)
        submission = ReviewSubmission(self.commit_id, body, [item for _, item in plan.inline], draft)
        try:
            submitted = self.adapter.submit_review(self.link.repository, self.link.pr_number, submission)
        except ForgeError as error:
            self.outcomes.extend(Outcome(_ids(comments), PublishStatus.FAILED, str(error)) for comments, _ in [*plan.inline, *plan.body_parts])
            return None
        for (comments, _), remote in zip(plan.inline, submitted.comments, strict=False):
            self.record(comments, remote)
            self.outcomes.append(Outcome(_ids(comments), PublishStatus.PUBLISHED, "Review comment", remote.url))
        for comments, _ in plan.body_parts:
            self.record(comments, RemoteComment(submitted.remote_id, submitted.url))
            self.outcomes.append(Outcome(_ids(comments), PublishStatus.PUBLISHED, "Part of the review body", submitted.url))
        return submitted.url

    def attempt(self, comments: list[Comment], action: Callable[[], RemoteComment]) -> None:
        try:
            remote = action()
        except ForgeError as error:
            self.outcomes.append(Outcome(_ids(comments), PublishStatus.FAILED, str(error)))
            return
        self.record(comments, remote)
        self.outcomes.append(Outcome(_ids(comments), PublishStatus.PUBLISHED, "Comment", remote.url))

    def update(self, comments: list[Comment], remote_id: str, body: str) -> None:
        try:
            self.adapter.update_comment(self.link.repository, remote_id, body)
        except ForgeError as error:
            self.outcomes.append(Outcome(_ids(comments), PublishStatus.FAILED, str(error)))
            return
        records = self.context.store.forge.published([comment.id for comment in comments])
        for comment in comments:
            records[comment.id].published_body_hash = body_hash(self.context, comment)
        self.outcomes.append(Outcome(_ids(comments), PublishStatus.UPDATED, "Edited on GitHub"))

    def record(self, comments: list[Comment], remote: RemoteComment) -> None:
        for comment in comments:
            record = PublishedComment(comment.id, self.adapter.provider, remote.remote_id, remote.url, body_hash(self.context, comment))
            self.context.store.forge.save_published(record)


def is_comment_id(remote_id: str | None) -> bool:
    return remote_id is not None and remote_id.isdigit()


def _is_edited(context: ReviewContext, comment: Comment, record: PublishedComment) -> bool:
    return record.published_body_hash != body_hash(context, comment)


def body_hash(context: ReviewContext, comment: Comment) -> str:
    return hashlib.sha256(render_comment(context, comment).encode()).hexdigest()


def _unit_location(view: ThreadView) -> str:
    thread = view.thread
    name = f"`{thread.qualified_name}`" if thread.qualified_name else "this file"
    end = view.end_file_line
    lines = f"lines {view.file_line}-{end}" if end is not None and end != view.file_line else f"line {view.file_line}"
    where = f"Outdated comment on {name}" if view.outdated or view.file_line is None else f"On {name}, {lines}"
    snippet = f"\n\n```\n{thread.line_text}\n```" if thread.line_text else ""
    return f"{where}:{snippet}\n\n"


def _ids(comments: list[Comment]) -> tuple[str, ...]:
    return tuple(comment.id for comment in comments)
