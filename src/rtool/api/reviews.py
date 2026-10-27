from fastapi import APIRouter, status

from rtool.api.deps import ContextDep, ReviewerDep, repo_of, resolve_revision
from rtool.api.schemas import RefreshIn, RefreshOut, ReviewDetailOut, ReviewerOut, SessionOut
from rtool.api.views import review_detail_out, revision_out
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
def refresh(body: RefreshIn, context: ContextDep) -> RefreshOut:
    result = refresh_review(context.store, context.review, open_repo(repo_of(context)), fetch=body.fetch, hooks=REVISION_HOOKS)
    context.store.commit()
    return RefreshOut(revision=revision_out(result.revision), created=result.created)


@router.post("/reviews/{review_id}/sessions", status_code=status.HTTP_201_CREATED)
def complete_review(context: ContextDep) -> SessionOut:
    revision = resolve_revision(context, None)
    review_session = context.store.reviews.add_session(ReviewSession(review_id=context.review.id, reviewer_id=context.reviewer.id, revision_id=revision.id))
    context.store.commit()
    return SessionOut(id=review_session.id, revision_id=review_session.revision_id, completed_at=review_session.completed_at)
