import re
from typing import Any

from fastapi import APIRouter, Request

from bussola.ai.base import AiCancelledError
from bussola.api.deps import ContextDep, repo_of, resolve_revision
from bussola.api.descriptions import ai_provider, ai_runner
from bussola.api.navigation import unit_at, units_by_path
from bussola.api.schemas import AiReviewIn, AiReviewLinkOut, AiReviewOut, AiReviewPartOut, AiReviewRunDetailOut, AiReviewRunOut, AiReviewStatusOut, CancelOut
from bussola.api.state import app_state
from bussola.config import load_repo_config
from bussola.errors import NotFoundError
from bussola.review.ai_review import AiReviewJob, AiReviewOutcome, RunStatus, ai_review_coverage, run_ai_review
from bussola.review.context import ReviewContext
from bussola.review.repos import open_repo
from bussola.review.review_tools import SIDES, ReviewTools
from bussola.storage.models import AiReviewRun

SUMMARY_LINK = re.compile(r"\]\(<?#(?P<side>after|before):(?P<path>[^)>\s]+):(?P<line>\d+)>?\)")

router = APIRouter(tags=["ai-review"])


@router.post("/reviews/{review_id}/ai-review")
def start_ai_review(context: ContextDep, body: AiReviewIn, request: Request) -> AiReviewOut:
    state = app_state(request)
    provider = ai_provider(state, context, body.target)
    revision = resolve_revision(context, None)
    git_repo = open_repo(repo_of(context))
    ignore = load_repo_config(git_repo.root).ignore
    try:
        with state.ai_calls.start(body.call_id) as cancellation, state.ai_reviews.start(context.review.id, cancellation) as report:
            snapshots = context.store.reviews.snapshots(revision.id)
            tools = ReviewTools(git_repo, revision, snapshots, state.navigator, ignore, cancellation)
            outcome = run_ai_review(AiReviewJob(context, revision, ai_runner(state, provider), tools, report, again=body.again))
    except AiCancelledError:
        outcome = AiReviewOutcome(reviewed=0, findings=0, failed=0, cancelled=True, error=None)
    return AiReviewOut(reviewed=outcome.reviewed, findings=outcome.findings, failed=outcome.failed, cancelled=outcome.cancelled, error=outcome.error)


@router.get("/reviews/{review_id}/ai-review")
def ai_review_status(context: ContextDep, request: Request) -> AiReviewStatusOut:
    progress = app_state(request).ai_reviews.progress(context.review.id)
    units, reviewed = ai_review_coverage(context, resolve_revision(context, None))
    runs = context.store.ai_reviews.count_runs(context.review.id)
    status = AiReviewStatusOut(running=progress is not None, units=units, reviewed_units=reviewed, runs=runs)
    if progress is None:
        return status
    return status.model_copy(update={"phase": progress.phase, "done": progress.done, "total": progress.total, "lookups": progress.lookups})


@router.post("/reviews/{review_id}/ai-review/cancel")
def cancel_ai_review(context: ContextDep, request: Request) -> CancelOut:
    return CancelOut(cancelled=app_state(request).ai_reviews.cancel(context.review.id))


@router.get("/reviews/{review_id}/ai-review/runs")
def list_ai_review_runs(context: ContextDep, request: Request) -> list[AiReviewRunOut]:
    running = app_state(request).ai_reviews.progress(context.review.id) is not None
    return [_run_out(run, running) for run in context.store.ai_reviews.runs(context.review.id)]


@router.get("/reviews/{review_id}/ai-review/runs/{run_id}")
def get_ai_review_run(context: ContextDep, run_id: int, request: Request) -> AiReviewRunDetailOut:
    run = context.store.ai_reviews.get_run(run_id)
    if run is None or run.review_id != context.review.id:
        raise NotFoundError("AI review run not found")
    brief = _run_out(run, app_state(request).ai_reviews.progress(context.review.id) is not None)
    parts: list[dict[str, Any]] = run.details.get("parts", [])
    shown = [AiReviewPartOut.model_validate(part) for part in parts]
    return AiReviewRunDetailOut(**brief.model_dump(), rating=run.details.get("rating"), parts=shown, links=_summary_links(context, parts))


def _summary_links(context: ReviewContext, parts: list[dict[str, Any]]) -> list[AiReviewLinkOut]:
    found = sorted({(match["side"], match["path"], int(match["line"])) for part in parts for match in SUMMARY_LINK.finditer(part.get("summary") or "")})
    if not found:
        return []
    revision = resolve_revision(context, None)
    units = {name: units_by_path(context, revision, side) for name, side in SIDES.items()}
    return [AiReviewLinkOut(path=path, side=SIDES[name], line=line, unit_id=unit_at(units[name], SIDES[name], path, line)) for name, path, line in found]


def _run_out(run: AiReviewRun, running: bool) -> AiReviewRunOut:
    status = RunStatus(run.status)
    if status == RunStatus.RUNNING and not running:
        status = RunStatus.INTERRUPTED
    return AiReviewRunOut(
        id=run.id,
        status=status,
        again=run.again,
        provider=run.provider,
        provider_label=run.provider_label,
        model=run.model,
        reviewed=run.reviewed,
        findings=run.findings,
        failed=run.failed,
        error=run.error,
        started_at=run.started_at,
        finished_at=run.finished_at,
    )
