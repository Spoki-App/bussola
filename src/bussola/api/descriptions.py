from pathlib import Path

from fastapi import APIRouter, Request

from bussola.ai.base import AiCancelledError, AiProvider
from bussola.ai.batch import BatchResult
from bussola.ai.config import load_user_config
from bussola.ai.runner import AiRunner
from bussola.ai.settings import load_ai_settings, require_target
from bussola.api.deps import ContextDep, repo_of, resolve_revision, snapshot_of
from bussola.api.schemas import AiCallIn, DescribeUnitIn, RateImpactOut, UnitDescriptionOut
from bussola.api.state import AppState, app_state
from bussola.review.context import ReviewContext
from bussola.review.descriptions import Impact, describe_unit, description_row, is_outdated, rate_units, stored_descriptions
from bussola.storage.models import UnitDescription

router = APIRouter(tags=["descriptions"])


@router.get("/reviews/{review_id}/descriptions")
def list_descriptions(context: ContextDep, revision_id: int | None = None) -> list[UnitDescriptionOut]:
    revision = resolve_revision(context, revision_id)
    snapshots = context.store.reviews.snapshots(revision.id, texts=False)
    found = stored_descriptions(snapshots, context.store.descriptions.descriptions(context.review.id))
    return [_description_out(snapshot.id, found[snapshot.id], is_outdated(found[snapshot.id], snapshot)) for snapshot in snapshots if snapshot.id in found]


@router.post("/reviews/{review_id}/units/{unit_id}/description")
def describe(context: ContextDep, unit_id: int, body: DescribeUnitIn, request: Request) -> UnitDescriptionOut:
    state = app_state(request)
    snapshot = snapshot_of(context, unit_id)
    provider = ai_provider(state, context, body.target)
    context.store.commit()
    with state.ai_calls.start(body.call_id) as cancellation:
        insight = describe_unit(snapshot, ai_runner(state, provider), cancellation, regenerate=body.regenerate)
    saved = context.store.descriptions.save(description_row(context, snapshot, provider, insight, insight.description))
    context.store.commit()
    return _description_out(unit_id, saved, outdated=False)


@router.post("/reviews/{review_id}/impact")
def rate_all(context: ContextDep, body: AiCallIn, request: Request) -> RateImpactOut:
    state = app_state(request)
    provider = ai_provider(state, context, body.target)
    snapshots = context.store.reviews.snapshots(resolve_revision(context, None).id)
    try:
        with state.ai_calls.start(body.call_id) as cancellation:
            outcome = rate_units(context, snapshots, ai_runner(state, provider), cancellation)
    except AiCancelledError:
        outcome = BatchResult[int, None](cancelled=True)
    return RateImpactOut(
        rated=len(outcome.results),
        failed=len(outcome.errors),
        cancelled=outcome.cancelled,
        error=outcome.stopped_by or next(iter(outcome.errors.values()), None),
    )


def ai_runner(state: AppState, provider: AiProvider) -> AiRunner:
    return AiRunner(provider, state.ai_cache, prompts=load_user_config(state.settings.config_file).ai.prompts.custom())


def ai_provider(state: AppState, context: ReviewContext, target: str) -> AiProvider:
    return state.ai_factory(require_target(load_ai_settings(state.settings.config_file, Path(repo_of(context).path)), target))


def _description_out(unit_id: int, description: UnitDescription, outdated: bool) -> UnitDescriptionOut:
    return UnitDescriptionOut(
        unit_id=unit_id,
        description=description.description,
        impact=Impact(description.impact),
        impact_reason=description.impact_reason,
        provider=description.provider,
        provider_label=description.provider_label,
        model=description.model,
        created_at=description.created_at,
        outdated=outdated,
    )
