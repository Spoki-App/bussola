from rtool.errors import ForbiddenError, InvalidRequestError, NotFoundError
from rtool.review.context import ReviewContext
from rtool.review.keys import key_of
from rtool.review.overview import approval_set
from rtool.review.rows import ROW_APPROVABLE_KINDS, Side, side_lines
from rtool.review.states import DONE_STATES, compute_statuses, snapshot_rows
from rtool.storage.models import Approval, Revision, RowApproval, UnitSnapshot, new_id, utcnow
from rtool.units.model import UnitKind

APPROVED_TEXT_LIMIT_BYTES = 1_000_000

type LineRange = tuple[int, int]


def approve_unit(context: ReviewContext, snapshot: UnitSnapshot) -> Approval:
    return context.store.approvals.add_approvals([_approval_for(context, snapshot)])[0]


def approve_file(context: ReviewContext, revision: Revision, path: str) -> list[Approval]:
    snapshots = [snapshot for snapshot in context.store.reviews.snapshots(revision.id) if snapshot.path == path]
    if not snapshots:
        raise NotFoundError(f"No changed units in {path}")
    statuses = compute_statuses(snapshots, approval_set(context))
    pending = [snapshot for snapshot in snapshots if statuses[snapshot.id].state not in DONE_STATES]
    return context.store.approvals.add_approvals([_approval_for(context, snapshot) for snapshot in pending])


def approve_rows(context: ReviewContext, snapshot: UnitSnapshot, head_range: LineRange | None, base_range: LineRange | None) -> list[RowApproval]:
    if UnitKind(snapshot.kind) not in ROW_APPROVABLE_KINDS:
        raise InvalidRequestError("Only module and file units can be approved by selection")
    file_lines = {side: [line.file_line for line in side_lines(snapshot, side)] for side in Side}
    ranges = {Side.HEAD: head_range, Side.BASE: base_range}
    already = approval_set(context).approved_rows_by_key().get(key_of(snapshot), set())
    selected = [row for row in snapshot_rows(snapshot) if _in_range(file_lines[row.side][row.index], ranges[row.side]) and row.row_hash not in already]
    if not selected:
        raise InvalidRequestError("The selection contains no changed lines that still need approval")
    selection_id = new_id()
    revision_id = snapshot.revision_id
    rows = [
        RowApproval(
            review_id=context.review.id,
            reviewer_id=context.reviewer.id,
            path=snapshot.path,
            kind=snapshot.kind,
            qualified_name=snapshot.qualified_name,
            side=row.side.value,
            row_hash=row.row_hash,
            line_text=row.text,
            selection_id=selection_id,
            revision_id=revision_id,
        )
        for row in selected
    ]
    return context.store.approvals.add_row_approvals(rows)


def revoke_approval(context: ReviewContext, approval_id: str) -> Approval:
    approval = context.store.approvals.get_approval(approval_id)
    if approval is None or approval.review_id != context.review.id:
        raise NotFoundError("Approval not found")
    if approval.reviewer_id != context.reviewer.id:
        raise ForbiddenError("You can only revoke your own approvals")
    if approval.revoked_at is None:
        approval.revoked_at = utcnow()
    return approval


def revoke_selection(context: ReviewContext, selection_id: str) -> list[RowApproval]:
    rows = [row for row in context.store.approvals.selection(selection_id) if row.review_id == context.review.id]
    if not rows:
        raise NotFoundError("Selection not found")
    if any(row.reviewer_id != context.reviewer.id for row in rows):
        raise ForbiddenError("You can only revoke your own approvals")
    revoked_at = utcnow()
    for row in rows:
        if row.revoked_at is None:
            row.revoked_at = revoked_at
    return rows


def _approval_for(context: ReviewContext, snapshot: UnitSnapshot) -> Approval:
    text = snapshot.head_text
    if text is not None and len(text.encode()) > APPROVED_TEXT_LIMIT_BYTES:
        text = None
    return Approval(
        review_id=context.review.id,
        reviewer_id=context.reviewer.id,
        path=snapshot.path,
        kind=snapshot.kind,
        qualified_name=snapshot.qualified_name,
        head_hash=snapshot.head_hash,
        base_hash=snapshot.base_hash,
        approved_text=text,
        revision_id=snapshot.revision_id,
    )


def _in_range(file_line: int | None, line_range: LineRange | None) -> bool:
    return file_line is not None and line_range is not None and line_range[0] <= file_line <= line_range[1]
