from fastapi import APIRouter, Request

from bussola.ai.base import AiCancelledError
from bussola.ai.runner import AiRunner
from bussola.api.deps import ContextDep, resolve_revision
from bussola.api.descriptions import ai_provider
from bussola.api.schemas import AiCallIn, AiReviewOut, AiReviewStatusOut
from bussola.api.state import app_state
from bussola.review.ai_review import AiReviewOutcome, reviewable_units, run_ai_review

router = APIRouter(tags=["ai-review"])


@router.post("/reviews/{review_id}/ai-review")
def start_ai_review(context: ContextDep, body: AiCallIn, request: Request) -> AiReviewOut:
    state = app_state(request)
    provider = ai_provider(state, context, body.target)
    revision = resolve_revision(context, None)
    with state.ai_reviews.start(context.review.id) as report:
        try:
            with state.ai_calls.start(body.call_id) as cancellation:
                outcome = run_ai_review(context, revision, AiRunner(provider, state.ai_cache), cancellation, report)
        except AiCancelledError:
            outcome = AiReviewOutcome(reviewed=0, findings=0, failed=0, cancelled=True, error=None)
    return AiReviewOut(reviewed=outcome.reviewed, findings=outcome.findings, failed=outcome.failed, cancelled=outcome.cancelled, error=outcome.error)


@router.get("/reviews/{review_id}/ai-review")
def ai_review_status(context: ContextDep, request: Request) -> AiReviewStatusOut:
    progress = app_state(request).ai_reviews.progress(context.review.id)
    units, pending = reviewable_units(context, resolve_revision(context, None))
    status = AiReviewStatusOut(running=progress is not None, units=len(units), reviewed_units=len(units) - len(pending))
    if progress is None:
        return status
    return status.model_copy(update={"phase": progress.phase, "done": progress.done, "total": progress.total})
