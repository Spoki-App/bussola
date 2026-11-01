from pathlib import Path

from fastapi import APIRouter, Request

from bussola.ai.settings import load_ai_settings, require_target
from bussola.api.deps import ContextDep, repo_of, resolve_revision, snapshot_of
from bussola.api.schemas import CancelOut, DescribeUnitIn, UnitDescriptionOut
from bussola.api.state import app_state
from bussola.review.descriptions import Impact, StoredDescription, change_hash, describe_unit, stored_descriptions
from bussola.storage.ai_cache import DatabaseAiCache
from bussola.storage.models import UnitDescription

router = APIRouter(tags=["descriptions"])
DESCRIBE_CALL = "describe_unit"


@router.get("/reviews/{review_id}/descriptions")
def list_descriptions(context: ContextDep, revision_id: int | None = None) -> list[UnitDescriptionOut]:
    revision = resolve_revision(context, revision_id)
    snapshots = context.store.reviews.snapshots(revision.id, texts=False)
    found = stored_descriptions(snapshots, context.store.descriptions.descriptions(context.review.id))
    return [_description_out(unit_id, stored) for unit_id, stored in found.items()]


@router.post("/reviews/{review_id}/units/{unit_id}/description")
def describe(context: ContextDep, unit_id: int, body: DescribeUnitIn, request: Request) -> UnitDescriptionOut:
    state = app_state(request)
    snapshot = snapshot_of(context, unit_id)
    settings = require_target(load_ai_settings(state.settings.config_file, Path(repo_of(context).path)), body.target)
    provider = state.ai_factory(settings)
    context.store.commit()
    with state.ai_calls.start((DESCRIBE_CALL, unit_id)) as cancellation:
        insight = describe_unit(snapshot, provider, DatabaseAiCache(state.database), cancellation, regenerate=body.regenerate)
    saved = context.store.descriptions.save(
        UnitDescription(
            review_id=context.review.id,
            revision_id=snapshot.revision_id,
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
    return _description_out(unit_id, StoredDescription(saved, outdated=False))


@router.post("/reviews/{review_id}/units/{unit_id}/description/cancel")
def cancel_description(context: ContextDep, unit_id: int, request: Request) -> CancelOut:
    snapshot_of(context, unit_id)
    return CancelOut(cancelled=app_state(request).ai_calls.cancel((DESCRIBE_CALL, unit_id)))


def _description_out(unit_id: int, stored: StoredDescription) -> UnitDescriptionOut:
    description = stored.description
    return UnitDescriptionOut(
        unit_id=unit_id,
        description=description.description,
        impact=Impact(description.impact),
        impact_reason=description.impact_reason,
        provider=description.provider,
        provider_label=description.provider_label,
        model=description.model,
        created_at=description.created_at,
        outdated=stored.outdated,
    )
