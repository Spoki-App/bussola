from fastapi import APIRouter, Request, status

from bussola.api.deps import ContextDep, ReviewerDep, repo_of, resolve_revision
from bussola.api.schemas import RefreshIn, RefreshOut, ReviewDetailOut, ReviewerOut, SessionOut, SyncOut
from bussola.api.state import app_state
from bussola.api.views import publish_out, review_detail_out, revision_out
from bussola.forge.review_sync import Refreshed, refresh_with_fetch, sync_and_publish
from bussola.review.repos import open_repo
from bussola.review.revisions import refresh_review
from bussola.storage.models import ReviewSession

router = APIRouter(tags=["reviews"])


@router.get("/me")
def get_me(reviewer: ReviewerDep) -> ReviewerOut:
    return ReviewerOut(id=reviewer.id, email=reviewer.email, name=reviewer.name)


@router.get("/reviews/{review_id}")
def get_review(context: ContextDep) -> ReviewDetailOut:
    return review_detail_out(context, repo_of(context))


@router.post("/reviews/{review_id}/refresh")
def refresh(body: RefreshIn, context: ContextDep, request: Request) -> RefreshOut:
    git_repo = open_repo(repo_of(context))
    if body.fetch:
        return _refresh_out(refresh_with_fetch(context, app_state(request).forge, git_repo))
    result = refresh_review(context.store, context.review, git_repo)
    context.store.commit()
    return _refresh_out(Refreshed(result))


@router.post("/reviews/{review_id}/sync")
def sync(context: ContextDep, request: Request) -> SyncOut:
    outcome = sync_and_publish(context, app_state(request).forge, open_repo(repo_of(context)))
    published = publish_out(outcome.published) if outcome.published else None
    return SyncOut(refresh=_refresh_out(outcome.refreshed), published=published, publish_error=outcome.publish_error, unsent_comments=outcome.unsent_comments)


def _refresh_out(refreshed: Refreshed) -> RefreshOut:
    return RefreshOut(revision=revision_out(refreshed.result.revision), created=refreshed.result.created, warning=refreshed.warning)


@router.post("/reviews/{review_id}/sessions", status_code=status.HTTP_201_CREATED)
def complete_review(context: ContextDep) -> SessionOut:
    revision = resolve_revision(context, None)
    review_session = context.store.reviews.add_session(ReviewSession(review_id=context.review.id, reviewer_id=context.reviewer.id, revision_id=revision.id))
    context.store.commit()
    return SessionOut(id=review_session.id, revision_id=review_session.revision_id, completed_at=review_session.completed_at)
