from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from rtool.review.anchoring import side_text
from rtool.review.keys import KeyTuple, key_of
from rtool.review.rows import ROW_APPROVABLE_KINDS, ChangedRow, Side, changed_rows
from rtool.storage.models import Approval, RowApproval, UnitSnapshot
from rtool.units.model import UnitKind


class UnitState(StrEnum):
    APPROVED = "approved"
    APPROVED_MOVED = "approved_moved"
    CHANGED = "changed"
    PARTIAL = "partial"
    REMOVED = "removed"
    NEW = "new"


TODO_STATES = frozenset({UnitState.NEW, UnitState.CHANGED, UnitState.PARTIAL, UnitState.REMOVED})
DONE_STATES = frozenset({UnitState.APPROVED, UnitState.APPROVED_MOVED})


class ApprovalAction(StrEnum):
    APPROVE = "approve"
    APPROVE_UNDER_NAME = "approve_under_name"
    CONFIRM_REMOVAL = "confirm_removal"
    REVOKE = "revoke"
    REVOKE_LINES = "revoke_lines"
    NONE = "none"


@dataclass(frozen=True)
class UnitStatus:
    state: UnitState
    approval: Approval | None = None
    base_changed: bool = False
    rows_total: int = 0
    approved_row_hashes: frozenset[str] = field(default_factory=frozenset)

    @property
    def is_todo(self) -> bool:
        return self.state in TODO_STATES

    def action(self, removed: bool) -> ApprovalAction:
        if self.state == UnitState.APPROVED:
            return ApprovalAction.REVOKE_LINES if self.approved_row_hashes else ApprovalAction.REVOKE
        if self.state == UnitState.APPROVED_MOVED:
            return ApprovalAction.NONE if removed else ApprovalAction.APPROVE_UNDER_NAME
        return ApprovalAction.CONFIRM_REMOVAL if self.state == UnitState.REMOVED else ApprovalAction.APPROVE


@dataclass(frozen=True)
class ApprovalSet:
    approvals: Sequence[Approval]
    row_approvals: Sequence[RowApproval]
    moment: datetime | None = None

    def active_by_key(self) -> dict[KeyTuple, Approval]:
        active: dict[KeyTuple, Approval] = {}
        for approval in sorted(self.approvals, key=lambda item: item.created_at):
            if _is_active(approval.created_at, approval.revoked_at, self.moment):
                active[key_of(approval)] = approval
        return active

    def approved_rows_by_key(self) -> dict[KeyTuple, set[str]]:
        rows: dict[KeyTuple, set[str]] = {}
        for row in self.row_approvals:
            if _is_active(row.created_at, row.revoked_at, self.moment):
                rows.setdefault(key_of(row), set()).add(row.row_hash)
        return rows


def snapshot_rows(snapshot: UnitSnapshot) -> list[ChangedRow]:
    if UnitKind(snapshot.kind) not in ROW_APPROVABLE_KINDS or (snapshot.base_text is None and snapshot.head_text is None):
        return []
    return changed_rows(side_text(snapshot, Side.BASE), side_text(snapshot, Side.HEAD))


def compute_statuses(snapshots: Iterable[UnitSnapshot], approval_set: ApprovalSet) -> dict[int, UnitStatus]:
    snapshots = list(snapshots)
    active = approval_set.active_by_key()
    approved_rows = approval_set.approved_rows_by_key()
    present = {key_of(snapshot) for snapshot in snapshots if snapshot.head_hash is not None}
    moved = {approval.head_hash: approval for key, approval in active.items() if approval.head_hash is not None and key not in present}
    statuses = {snapshot.id: _status(snapshot, active.get(key_of(snapshot)), moved, approved_rows.get(key_of(snapshot), set())) for snapshot in snapshots}
    return _with_moved_sources(snapshots, statuses)


def _with_moved_sources(snapshots: list[UnitSnapshot], statuses: dict[int, UnitStatus]) -> dict[int, UnitStatus]:
    added = [snapshot for snapshot in snapshots if snapshot.base_hash is None]
    done_targets = {snapshot.head_hash: statuses[snapshot.id] for snapshot in added if statuses[snapshot.id].state in DONE_STATES}
    for snapshot in snapshots:
        target = done_targets.get(snapshot.base_hash) if snapshot.head_hash is None and snapshot.base_hash is not None else None
        if target is not None and statuses[snapshot.id].state not in DONE_STATES:
            statuses[snapshot.id] = UnitStatus(UnitState.APPROVED_MOVED, target.approval)
    return statuses


def _status(snapshot: UnitSnapshot, approval: Approval | None, moved: dict[str, Approval], approved_rows: set[str]) -> UnitStatus:
    if approval is not None and approval.head_hash == snapshot.head_hash:
        return UnitStatus(UnitState.APPROVED, approval, base_changed=approval.base_hash != snapshot.base_hash)
    if approval is None and snapshot.head_hash is not None and (moved_approval := moved.get(snapshot.head_hash)) is not None:
        return UnitStatus(UnitState.APPROVED_MOVED, moved_approval)
    if approved_rows:
        row_hashes = {row.row_hash for row in snapshot_rows(snapshot)}
        covered = frozenset(row_hashes & approved_rows)
        if covered and len(covered) == len(row_hashes):
            return UnitStatus(UnitState.APPROVED, approval, rows_total=len(row_hashes), approved_row_hashes=covered)
        if covered:
            return UnitStatus(UnitState.PARTIAL, approval, rows_total=len(row_hashes), approved_row_hashes=covered)
    if approval is not None:
        return UnitStatus(UnitState.CHANGED, approval)
    return UnitStatus(UnitState.REMOVED if snapshot.head_hash is None else UnitState.NEW)


def _is_active(created_at: datetime, revoked_at: datetime | None, moment: datetime | None) -> bool:
    if moment is None:
        return revoked_at is None
    return created_at <= moment and (revoked_at is None or revoked_at > moment)
