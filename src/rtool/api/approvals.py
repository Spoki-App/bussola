from fastapi import APIRouter, status

from rtool.api.deps import ContextDep, resolve_revision, snapshot_of
from rtool.api.schemas import ApprovalIn, ApprovalOut, ApprovalResultOut, RowApprovalOut
from rtool.api.views import approval_out, row_approval_out
from rtool.review.approvals import approve_file, approve_rows, approve_unit, revoke_approval, revoke_selection

router = APIRouter(tags=["approvals"])


@router.post("/reviews/{review_id}/approvals", status_code=status.HTTP_201_CREATED)
def create_approval(body: ApprovalIn, context: ContextDep) -> ApprovalResultOut:
    result = ApprovalResultOut(approvals=[], row_approvals=[])
    if body.path is not None:
        result.approvals = [approval_out(approval) for approval in approve_file(context, resolve_revision(context, None), body.path)]
    elif body.unit_id is not None:
        snapshot = snapshot_of(context, body.unit_id)
        if body.head_range or body.base_range:
            result.row_approvals = [row_approval_out(row) for row in approve_rows(context, snapshot, body.head_range, body.base_range)]
        else:
            result.approvals = [approval_out(approve_unit(context, snapshot))]
    context.store.commit()
    return result


@router.delete("/reviews/{review_id}/approvals/{approval_id}")
def delete_approval(context: ContextDep, approval_id: str) -> ApprovalOut:
    approval = revoke_approval(context, approval_id)
    context.store.commit()
    return approval_out(approval)


@router.delete("/reviews/{review_id}/row-approvals/{selection_id}")
def delete_row_approvals(context: ContextDep, selection_id: str) -> list[RowApprovalOut]:
    rows = revoke_selection(context, selection_id)
    context.store.commit()
    return [row_approval_out(row) for row in rows]
