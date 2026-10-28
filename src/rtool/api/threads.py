from typing import Annotated

from fastapi import APIRouter, Depends, status

from rtool.api.deps import ReviewerDep, StoreDep, resolve_revision, snapshot_of
from rtool.api.schemas import CommentIn, CommentOut, ReviewerOut, ThreadAnchorOut, ThreadDeletedOut, ThreadIn, ThreadOut, ThreadPatch
from rtool.errors import NotFoundError
from rtool.review.anchoring import line_count
from rtool.review.context import ReviewContext
from rtool.review.rows import Side
from rtool.review.threads import (
    NewThread,
    ThreadScope,
    ThreadStatus,
    ThreadView,
    add_comment,
    can_delete,
    create_thread,
    delete_comment,
    delete_thread,
    edit_comment,
    get_thread,
    thread_views,
)
from rtool.storage.models import Comment, PublishedComment, Reviewer
from rtool.storage.repositories import Store

router = APIRouter(tags=["threads"])


def review_context_for(review_id: int, store: StoreDep, reviewer: ReviewerDep) -> ReviewContext:
    review = store.reviews.get_review(review_id)
    if review is None:
        raise NotFoundError(f"Review {review_id} not found")
    return ReviewContext(store, review, reviewer)


def thread_context(thread_id: str, store: StoreDep, reviewer: ReviewerDep) -> ReviewContext:
    thread = store.threads.get_thread(thread_id)
    if thread is None:
        raise NotFoundError("Thread not found")
    return review_context_for(thread.review_id, store, reviewer)


def comment_context(comment_id: str, store: StoreDep, reviewer: ReviewerDep) -> ReviewContext:
    comment = store.threads.get_comment(comment_id)
    if comment is None:
        raise NotFoundError("Comment not found")
    return thread_context(comment.thread_id, store, reviewer)


ReviewContextDep = Annotated[ReviewContext, Depends(review_context_for)]
ThreadContextDep = Annotated[ReviewContext, Depends(thread_context)]
CommentContextDep = Annotated[ReviewContext, Depends(comment_context)]


@router.get("/reviews/{review_id}/threads")
def list_threads(context: ReviewContextDep, revision_id: int | None = None) -> list[ThreadOut]:
    revision = resolve_revision(context, revision_id)
    return [thread_out(context, view) for view in thread_views(context, revision)]


@router.post("/reviews/{review_id}/threads", status_code=status.HTTP_201_CREATED)
def post_thread(body: ThreadIn, context: ReviewContextDep) -> ThreadOut:
    snapshot = snapshot_of(context, body.unit_id) if body.unit_id is not None else None
    revision = context.store.reviews.get_revision(snapshot.revision_id) if snapshot else resolve_revision(context, None)
    if revision is None:
        raise NotFoundError("Revision not found")
    request = NewThread(body.scope, body.body, snapshot, body.path, body.side, body.line_offset, body.line_count)
    thread = create_thread(context, revision, request)
    context.store.commit()
    return _single_view(context, thread.id, revision.id)


@router.post("/threads/{thread_id}/comments", status_code=status.HTTP_201_CREATED)
def post_comment(thread_id: str, body: CommentIn, context: ThreadContextDep) -> CommentOut:
    comment = add_comment(context, get_thread(context, thread_id), body.body)
    context.store.commit()
    return comment_out(context, comment)


@router.patch("/threads/{thread_id}")
def patch_thread(thread_id: str, body: ThreadPatch, context: ThreadContextDep) -> ThreadOut:
    thread = get_thread(context, thread_id)
    thread.status = body.status.value
    context.store.commit()
    return _single_view(context, thread.id, None)


@router.delete("/threads/{thread_id}")
def remove_thread(thread_id: str, context: ThreadContextDep) -> ThreadDeletedOut:
    thread = delete_thread(context, get_thread(context, thread_id))
    context.store.commit()
    return ThreadDeletedOut(id=thread.id, deleted=True)


@router.patch("/comments/{comment_id}")
def patch_comment(comment_id: str, body: CommentIn, context: CommentContextDep) -> CommentOut:
    comment = edit_comment(context, _comment(context.store, comment_id), body.body)
    context.store.commit()
    return comment_out(context, comment)


@router.delete("/comments/{comment_id}")
def remove_comment(comment_id: str, context: CommentContextDep) -> CommentOut:
    comment = delete_comment(context, _comment(context.store, comment_id))
    context.store.commit()
    return comment_out(context, comment)


def thread_out(context: ReviewContext, view: ThreadView) -> ThreadOut:
    thread, anchor = view.thread, view.anchor
    published = context.store.forge.published([comment.id for comment in view.comments])
    return ThreadOut(
        id=thread.id,
        scope=ThreadScope(thread.scope),
        path=thread.path,
        kind=thread.kind,
        qualified_name=thread.qualified_name,
        side=Side(thread.side) if thread.side else None,
        status=ThreadStatus(thread.status),
        created_by=_reviewer_out(context.store, thread.created_by),
        created_at=thread.created_at,
        line_text=thread.line_text,
        line_count=line_count(thread),
        context_before=thread.context_before,
        context_after=thread.context_after,
        anchor=None
        if anchor is None
        else ThreadAnchorOut(
            revision_id=anchor.revision_id,
            line_offset=anchor.line_offset,
            outdated=anchor.outdated,
            unit_id=view.unit_id,
            file_line=view.file_line,
            end_file_line=view.end_file_line,
        ),
        comments=[comment_out(context, comment, published.get(comment.id)) for comment in view.comments],
        can_delete=can_delete(context, thread, view.comments),
    )


def comment_out(context: ReviewContext, comment: Comment, published: PublishedComment | None = None) -> CommentOut:
    deleted = comment.deleted_at is not None
    return CommentOut(
        id=comment.id,
        thread_id=comment.thread_id,
        author=_reviewer_out(context.store, comment.author_id),
        body="" if deleted else comment.body,
        created_at=comment.created_at,
        edited_at=comment.edited_at,
        deleted=deleted,
        mine=comment.author_id == context.reviewer.id,
        remote_url=published.remote_url if published else None,
    )


def _single_view(context: ReviewContext, thread_id: str, revision_id: int | None) -> ThreadOut:
    revision = resolve_revision(context, revision_id)
    view = next(view for view in thread_views(context, revision) if view.thread.id == thread_id)
    return thread_out(context, view)


def _comment(store: Store, comment_id: str) -> Comment:
    comment = store.threads.get_comment(comment_id)
    if comment is None:
        raise NotFoundError("Comment not found")
    return comment


def _reviewer_out(store: Store, reviewer_id: int) -> ReviewerOut:
    reviewer = store.reviews.get_reviewer(reviewer_id) or Reviewer(email="unknown", name="Unknown")
    return ReviewerOut(id=reviewer_id, email=reviewer.email, name=reviewer.name)
