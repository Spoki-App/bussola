from pathlib import Path

from fastapi import APIRouter, Request

from bussola.ai.base import AiProvider
from bussola.ai.batch import run_batch
from bussola.ai.settings import load_ai_settings, require_target
from bussola.api.deps import ContextDep, repo_of, resolve_revision, snapshot_of
from bussola.api.schemas import AiCallIn, DescribeUnitIn, RateImpactOut, UnitDescriptionOut
from bussola.api.state import app_state
from bussola.review.context import ReviewContext
from bussola.review.descriptions import (
    Impact,
    ImpactRating,
    UnitInsight,
    change_hash,
    describe_unit,
    is_outdated,
    rate_impact,
    stored_descriptions,
    unrated,
)
from bussola.storage.models import UnitDescription, UnitSnapshot

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
    provider = _provider(context, request, body.target)
    context.store.commit()
    with state.ai_calls.start(body.call_id) as cancellation:
        insight = describe_unit(snapshot, provider, state.ai_cache, cancellation, regenerate=body.regenerate)
    saved = context.store.descriptions.save(_row(context, snapshot, provider, insight, insight.description))
    context.store.commit()
    return _description_out(unit_id, saved, outdated=False)


@router.post("/reviews/{review_id}/impact")
def rate_units(context: ContextDep, body: AiCallIn, request: Request) -> RateImpactOut:
    state = app_state(request)
    provider = _provider(context, request, body.target)
    snapshots = context.store.reviews.snapshots(resolve_revision(context, None).id)
    pending = {snapshot.id: snapshot for snapshot in unrated(snapshots, context.store.descriptions.descriptions(context.review.id))}
    context.store.commit()
    with state.ai_calls.start(body.call_id) as cancellation:

        def rate(unit_id: int) -> None:
            snapshot = pending[unit_id]
            rating = rate_impact(snapshot, provider, state.ai_cache, cancellation)
            context.store.descriptions.save(_row(context, snapshot, provider, rating, None), replace=False)
            context.store.commit()

        outcome = run_batch(list(pending), rate, cancellation)
    return RateImpactOut(
        rated=len(outcome.results),
        failed=len(outcome.errors),
        cancelled=outcome.cancelled,
        error=outcome.stopped_by or next(iter(outcome.errors.values()), None),
    )


def _provider(context: ReviewContext, request: Request, target: str) -> AiProvider:
    state = app_state(request)
    return state.ai_factory(require_target(load_ai_settings(state.settings.config_file, Path(repo_of(context).path)), target))


def _row(context: ReviewContext, snapshot: UnitSnapshot, provider: AiProvider, rating: ImpactRating | UnitInsight, description: str | None) -> UnitDescription:
    return UnitDescription(
        review_id=context.review.id,
        path=snapshot.path,
        kind=snapshot.kind,
        qualified_name=snapshot.qualified_name,
        change_hash=change_hash(snapshot),
        description=description,
        impact=rating.impact,
        impact_reason=rating.impact_reason,
        provider=provider.name,
        provider_label=provider.label,
        model=provider.model,
    )


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
