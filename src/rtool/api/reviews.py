from fastapi import APIRouter, Request, status

from rtool.api.deps import ContextDep, ReviewerDep, repo_of, resolve_revision
from rtool.api.schemas import RefreshIn, RefreshOut, ReviewDetailOut, ReviewerOut, SessionOut
from rtool.api.state import app_state
from rtool.api.views import review_detail_out, revision_out
from rtool.forge.conversation import import_conversation
from rtool.forge.pulls import PULL_REF_PREFIX, ForgeSession, sync_review
from rtool.review.hooks import REVISION_HOOKS
from rtool.review.repos import open_repo
from rtool.review.revisions import refresh_review
from rtool.storage.models import ReviewSession

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
    link = context.store.forge.link(context.review.id)
    pull_review = body.fetch and link is not None and context.review.head_ref.startswith(PULL_REF_PREFIX)
    adapter = app_state(request).forge
    session = ForgeSession(context.store, adapter, git_repo, context.reviewer)
    synced = sync_review(session, context.review, link) if pull_review and link is not None else None
    result = synced or refresh_review(context.store, context.review, git_repo, fetch=body.fetch and not pull_review, hooks=REVISION_HOOKS)
    if body.fetch and link is not None and not pull_review:
        import_conversation(context, adapter, link, result.revision)
    context.store.commit()
    return RefreshOut(revision=revision_out(result.revision), created=result.created)


@router.post("/reviews/{review_id}/sessions", status_code=status.HTTP_201_CREATED)
def complete_review(context: ContextDep) -> SessionOut:
    revision = resolve_revision(context, None)
    review_session = context.store.reviews.add_session(ReviewSession(review_id=context.review.id, reviewer_id=context.reviewer.id, revision_id=revision.id))
    context.store.commit()
    return SessionOut(id=review_session.id, revision_id=review_session.revision_id, completed_at=review_session.completed_at)
