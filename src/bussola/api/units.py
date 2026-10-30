from fastapi import APIRouter, Response

from bussola.api.deps import ContextDep, repo_of, resolve_revision, snapshot_of
from bussola.api.images import image_response
from bussola.api.schemas import DiffOut, DiffRowOut, UnitOut
from bussola.api.views import unit_out
from bussola.errors import InvalidRequestError, NotFoundError
from bussola.review.diffs import DiffMode, build_diff, choose_diff_mode
from bussola.review.images import image_type
from bussola.review.keys import key_of
from bussola.review.modules import ModulePaths
from bussola.review.overview import UnitFilter, approval_set, unit_views
from bussola.review.repos import open_repo
from bussola.review.rows import Side
from bussola.review.states import compute_statuses
from bussola.review.threads_count import open_thread_counts

router = APIRouter(tags=["units"])


@router.get("/reviews/{review_id}/units")
def list_units(context: ContextDep, revision_id: int | None = None, filter: UnitFilter = UnitFilter.ALL) -> list[UnitOut]:  # noqa: A002
    revision = resolve_revision(context, revision_id)
    threads = open_thread_counts(context.store.threads.threads(context.review.id))
    modules = ModulePaths(repo_of(context), revision)
    return [unit_out(view, threads.get(key_of(view.snapshot), 0), modules) for view in unit_views(context, revision, filter)]


@router.get("/reviews/{review_id}/units/{unit_id}/diff")
def get_diff(context: ContextDep, unit_id: int, mode: DiffMode | None = None) -> DiffOut:
    snapshot = snapshot_of(context, unit_id)
    approvals = approval_set(context)
    status = compute_statuses([snapshot], approvals)[snapshot.id]
    choice = choose_diff_mode(snapshot, status.approval, mode)
    diff = build_diff(snapshot, choice.effective, status.approval)
    selections = {row.row_hash: row.selection_id for row in approvals.row_approvals if key_of(row) == key_of(snapshot) and row.revoked_at is None}
    rows = [
        DiffRowOut(
            change=row.change,
            old_index=row.old_index,
            new_index=row.new_index,
            old_line=row.old_line,
            new_line=row.new_line,
            text=row.text,
            row_hash=row.row_hash,
            approved=row.row_hash is not None and row.row_hash in status.approved_row_hashes,
            selection_id=selections.get(row.row_hash) if row.row_hash else None,
            placeholder=row.placeholder,
        )
        for row in diff.rows
    ]
    return DiffOut(
        unit_id=snapshot.id,
        mode=choice.effective,
        available_modes=choice.available,
        approved_text_unavailable=choice.approved_text_unavailable,
        binary=diff.binary,
        unified=diff.unified,
        rows=rows,
    )


@router.get("/reviews/{review_id}/units/{unit_id}/image")
def get_image(context: ContextDep, unit_id: int, side: Side) -> Response:
    snapshot = snapshot_of(context, unit_id)
    path = snapshot.old_path or snapshot.path if side == Side.BASE else snapshot.path
    media_type = image_type(path)
    revision = context.store.reviews.get_revision(snapshot.revision_id)
    if media_type is None or revision is None:
        raise InvalidRequestError(f"{path} is not an image bussola can show")
    commit = revision.merge_base_sha if side == Side.BASE else revision.head_sha
    data = open_repo(repo_of(context)).file_at(commit, path)
    if data is None:
        raise NotFoundError(f"{path} does not exist on the {side.value} side")
    return image_response(data, media_type)
