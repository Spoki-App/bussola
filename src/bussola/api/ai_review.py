from fastapi import APIRouter, Request

from bussola.ai.base import AiCancelledError
from bussola.ai.runner import AiRunner
from bussola.api.deps import ContextDep, repo_of, resolve_revision
from bussola.api.descriptions import ai_provider
from bussola.api.schemas import AiCallIn, AiReviewOut, AiReviewStatusOut, CancelOut
from bussola.api.state import app_state
from bussola.config import load_repo_config
from bussola.review.ai_review import AiReviewJob, AiReviewOutcome, ai_review_coverage, run_ai_review
from bussola.review.repos import open_repo
from bussola.review.review_tools import ReviewTools

router = APIRouter(tags=["ai-review"])


@router.post("/reviews/{review_id}/ai-review")
def start_ai_review(context: ContextDep, body: AiCallIn, request: Request) -> AiReviewOut:
    state = app_state(request)
    provider = ai_provider(state, context, body.target)
    revision = resolve_revision(context, None)
    git_repo = open_repo(repo_of(context))
    ignore = load_repo_config(git_repo.root).ignore
    try:
        with state.ai_calls.start(body.call_id) as cancellation, state.ai_reviews.start(context.review.id, cancellation) as report:
            snapshots = context.store.reviews.snapshots(revision.id)
            tools = ReviewTools(git_repo, revision, snapshots, state.navigator, ignore, cancellation)
            outcome = run_ai_review(AiReviewJob(context, revision, AiRunner(provider, state.ai_cache), tools, report))
    except AiCancelledError:
        outcome = AiReviewOutcome(reviewed=0, findings=0, failed=0, cancelled=True, error=None)
    return AiReviewOut(reviewed=outcome.reviewed, findings=outcome.findings, failed=outcome.failed, cancelled=outcome.cancelled, error=outcome.error)


@router.get("/reviews/{review_id}/ai-review")
def ai_review_status(context: ContextDep, request: Request) -> AiReviewStatusOut:
    progress = app_state(request).ai_reviews.progress(context.review.id)
    units, reviewed = ai_review_coverage(context, resolve_revision(context, None))
    status = AiReviewStatusOut(running=progress is not None, units=units, reviewed_units=reviewed)
    if progress is None:
        return status
    return status.model_copy(update={"phase": progress.phase, "done": progress.done, "total": progress.total, "lookups": progress.lookups})


@router.post("/reviews/{review_id}/ai-review/cancel")
def cancel_ai_review(context: ContextDep, request: Request) -> CancelOut:
    return CancelOut(cancelled=app_state(request).ai_reviews.cancel(context.review.id))
