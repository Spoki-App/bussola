from pathlib import Path

from fastapi import APIRouter, Request

from bussola.ai.settings import load_ai_settings, require_target
from bussola.api.deps import ContextDep, repo_of, resolve_revision, snapshot_of
from bussola.api.schemas import CancelOut, DescribeUnitIn, UnitDescriptionOut
from bussola.api.state import app_state
from bussola.review.descriptions import DESCRIBE_UNIT, Impact, change_hash, describe_unit, is_outdated, stored_descriptions
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
    settings = require_target(load_ai_settings(state.settings.config_file, Path(repo_of(context).path)), body.target)
    provider = state.ai_factory(settings)
    context.store.commit()
    with state.ai_calls.start((DESCRIBE_UNIT.name, unit_id)) as cancellation:
        insight = describe_unit(snapshot, provider, state.ai_cache, cancellation, regenerate=body.regenerate)
    saved = context.store.descriptions.save(
        UnitDescription(
            review_id=context.review.id,
            path=snapshot.path,
            kind=snapshot.kind,
            qualified_name=snapshot.qualified_name,
            change_hash=change_hash(snapshot),
            description=insight.description,
            impact=insight.impact,
            impact_reason=insight.impact_reason,
            provider=provider.name,
            provider_label=provider.label,
            model=provider.model,
        )
    )
    context.store.commit()
    return _description_out(unit_id, saved, outdated=False)


@router.post("/reviews/{review_id}/units/{unit_id}/description/cancel")
def cancel_description(context: ContextDep, unit_id: int, request: Request) -> CancelOut:
    snapshot_of(context, unit_id)
    return CancelOut(cancelled=app_state(request).ai_calls.cancel((DESCRIBE_UNIT.name, unit_id)))


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
