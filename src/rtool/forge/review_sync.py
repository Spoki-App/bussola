from dataclasses import dataclass

from rtool.errors import ConflictError, InvalidRequestError
from rtool.forge.base import ForgeAdapter, ForgeError
from rtool.forge.conversation import import_conversation
from rtool.forge.publish import PublishResult, pending_comment_count, publish_comments
from rtool.forge.pulls import ForgeSession, is_pull_request_review, sync_review
from rtool.git import GitError, GitRepo, InvalidRefError
from rtool.review.context import ReviewContext
from rtool.review.revisions import RefreshResult, fetch_review_remotes, refresh_review

FETCH_ERRORS = (ForgeError, GitError, InvalidRefError, InvalidRequestError, ConflictError)
PUBLISH_ERRORS = (ForgeError, ConflictError)


@dataclass(frozen=True)
class Refreshed:
    result: RefreshResult
    warning: str | None = None


@dataclass(frozen=True)
class SyncOutcome:
    refreshed: Refreshed
    published: PublishResult | None
    publish_error: str | None
    unsent_comments: int


def refresh_with_fetch(context: ReviewContext, adapter: ForgeAdapter, git_repo: GitRepo) -> Refreshed:
    fetched: RefreshResult | None = None
    warning = None
    try:
        fetched = _fetch_and_refresh(context, adapter, git_repo)
    except FETCH_ERRORS as error:
        context.store.session.rollback()
        warning = f"Could not fetch ({error}). Checked the local branch instead."
    result = fetched or refresh_review(context.store, context.review, git_repo)
    context.store.commit()
    return Refreshed(result, warning)


def sync_and_publish(context: ReviewContext, adapter: ForgeAdapter, git_repo: GitRepo) -> SyncOutcome:
    refreshed = refresh_with_fetch(context, adapter, git_repo)
    revision = refreshed.result.revision
    published: PublishResult | None = None
    publish_error = None
    if context.store.forge.link(context.review.id) is not None and pending_comment_count(context, revision) > 0:
        try:
            published = publish_comments(context, adapter, revision, draft=False)
            context.store.commit()
        except PUBLISH_ERRORS as error:
            context.store.session.rollback()
            publish_error = str(error)
    return SyncOutcome(refreshed, published, publish_error, pending_comment_count(context, revision))


def _fetch_and_refresh(context: ReviewContext, adapter: ForgeAdapter, git_repo: GitRepo) -> RefreshResult | None:
    link = context.store.forge.link(context.review.id)
    if link is not None and is_pull_request_review(context.review):
        return sync_review(ForgeSession(context.store, adapter, git_repo, context.reviewer), context.review, link)
    fetch_review_remotes(git_repo, context.review)
    result = refresh_review(context.store, context.review, git_repo)
    if link is not None:
        import_conversation(context, adapter, link, result.revision)
    return result
