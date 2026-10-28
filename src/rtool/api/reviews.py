from fastapi import APIRouter, Request, status

from rtool.api.deps import ContextDep, ReviewerDep, repo_of, resolve_revision
from rtool.api.schemas import PublishOut, RefreshIn, RefreshOut, ReviewDetailOut, ReviewerOut, SessionOut, SyncOut
from rtool.api.state import app_state
from rtool.api.views import publish_out, review_detail_out, revision_out
from rtool.errors import ConflictError, InvalidRequestError
from rtool.forge.base import ForgeAdapter, ForgeError
from rtool.forge.conversation import import_conversation
from rtool.forge.publish import pending_comment_count, publish_comments
from rtool.forge.pulls import PULL_REF_PREFIX, ForgeSession, sync_review
from rtool.git import GitError, GitRepo, InvalidRefError
from rtool.review.context import ReviewContext
from rtool.review.hooks import REVISION_HOOKS
from rtool.review.repos import open_repo
from rtool.review.revisions import RefreshResult, fetch_review_remotes, refresh_review
from rtool.storage.models import ReviewSession

router = APIRouter(tags=["reviews"])

FETCH_ERRORS = (ForgeError, GitError, InvalidRefError, InvalidRequestError, ConflictError)


@router.get("/me")
def get_me(reviewer: ReviewerDep) -> ReviewerOut:
    return ReviewerOut(id=reviewer.id, email=reviewer.email, name=reviewer.name)


@router.get("/reviews/{review_id}")
def get_review(context: ContextDep) -> ReviewDetailOut:
    return review_detail_out(context, repo_of(context))


@router.post("/reviews/{review_id}/refresh")
def refresh(body: RefreshIn, context: ContextDep, request: Request) -> RefreshOut:
    return _refresh(context, request, fetch=body.fetch)


@router.post("/reviews/{review_id}/sync")
def sync(context: ContextDep, request: Request) -> SyncOut:
    refreshed = _refresh(context, request, fetch=True)
    revision = resolve_revision(context, None)
    published: PublishOut | None = None
    publish_error = None
    if context.store.forge.link(context.review.id) is not None and pending_comment_count(context, revision) > 0:
        try:
            published = publish_out(publish_comments(context, app_state(request).forge, revision, draft=False))
            context.store.commit()
        except (ForgeError, ConflictError) as error:
            context.store.session.rollback()
            publish_error = str(error)
    return SyncOut(refresh=refreshed, published=published, publish_error=publish_error, unsent_comments=pending_comment_count(context, revision))


def _refresh(context: ReviewContext, request: Request, *, fetch: bool) -> RefreshOut:
    git_repo = open_repo(repo_of(context))
    fetched: RefreshResult | None = None
    warning = None
    if fetch:
        try:
            fetched = _fetch_and_refresh(context, app_state(request).forge, git_repo)
        except FETCH_ERRORS as error:
            context.store.session.rollback()
            warning = f"Could not fetch ({error}). Checked the local branch instead."
    result = fetched or refresh_review(context.store, context.review, git_repo, hooks=REVISION_HOOKS)
    context.store.commit()
    return RefreshOut(revision=revision_out(result.revision), created=result.created, warning=warning)


def _fetch_and_refresh(context: ReviewContext, adapter: ForgeAdapter, git_repo: GitRepo) -> RefreshResult | None:
    link = context.store.forge.link(context.review.id)
    if link is not None and context.review.head_ref.startswith(PULL_REF_PREFIX):
        return sync_review(ForgeSession(context.store, adapter, git_repo, context.reviewer), context.review, link)
    fetch_review_remotes(git_repo, context.review)
    result = refresh_review(context.store, context.review, git_repo, hooks=REVISION_HOOKS)
    if link is not None:
        import_conversation(context, adapter, link, result.revision)
    return result


@router.post("/reviews/{review_id}/sessions", status_code=status.HTTP_201_CREATED)
def complete_review(context: ContextDep) -> SessionOut:
    revision = resolve_revision(context, None)
    review_session = context.store.reviews.add_session(ReviewSession(review_id=context.review.id, reviewer_id=context.reviewer.id, revision_id=revision.id))
    context.store.commit()
    return SessionOut(id=review_session.id, revision_id=review_session.revision_id, completed_at=review_session.completed_at)
