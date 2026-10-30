from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from bussola.review.context import ReviewContext
from bussola.review.keys import KeyTuple, key_of
from bussola.review.states import ApprovalSet, UnitState, UnitStatus, compute_statuses
from bussola.storage.models import Revision, UnitSnapshot


class UnitFilter(StrEnum):
    ALL = "all"
    TODO = "todo"
    SINCE_LAST = "since_last"


@dataclass(frozen=True)
class UnitView:
    snapshot: UnitSnapshot
    status: UnitStatus


def approval_set(context: ReviewContext, moment: datetime | None = None) -> ApprovalSet:
    approvals = context.store.approvals
    review_id, reviewer_id = context.review.id, context.reviewer.id
    return ApprovalSet(approvals.approvals(review_id, reviewer_id), approvals.row_approvals(review_id, reviewer_id), moment)


def unit_views(context: ReviewContext, revision: Revision, unit_filter: UnitFilter = UnitFilter.ALL, *, texts: bool = True) -> list[UnitView]:
    snapshots = context.store.reviews.snapshots(revision.id, texts=texts)
    statuses = compute_statuses(snapshots, approval_set(context))
    views = [UnitView(snapshot, statuses[snapshot.id]) for snapshot in snapshots]
    if unit_filter == UnitFilter.TODO:
        return [view for view in views if view.status.is_todo]
    if unit_filter == UnitFilter.SINCE_LAST:
        seen = seen_at_last_session(context)
        return [view for view in views if view.status.is_todo and (key_of(view.snapshot), view.snapshot.head_hash) not in seen]
    return views


def seen_at_last_session(context: ReviewContext) -> set[tuple[KeyTuple, str | None]]:
    session = context.store.reviews.last_session(context.review.id, context.reviewer.id)
    if session is None:
        return set()
    snapshots = context.store.reviews.snapshots(session.revision_id)
    statuses = compute_statuses(snapshots, approval_set(context, session.completed_at))
    return {(key_of(snapshot), snapshot.head_hash) for snapshot in snapshots if statuses[snapshot.id].is_todo}


def count_states(views: list[UnitView]) -> dict[UnitState, int]:
    counts = Counter(view.status.state for view in views)
    return {state: counts.get(state, 0) for state in UnitState}
