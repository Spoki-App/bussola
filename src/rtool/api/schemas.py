from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from rtool.review.diffs import DiffMode
from rtool.review.rows import LineChange
from rtool.review.scope import ChangeType
from rtool.review.states import UnitState

LineRangeIn = Annotated[tuple[int, int], Field(description="Inclusive file line range")]


class HealthOut(BaseModel):
    status: str


class ReviewerOut(BaseModel):
    id: int
    email: str
    name: str


class RepoIn(BaseModel):
    path: str = Field(min_length=1)


class RepoOut(BaseModel):
    id: int
    path: str
    name: str
    root_commit: str
    missing: bool


class RefsOut(BaseModel):
    local: list[str]
    remote: list[str]
    default_base: str | None


class ReviewIn(BaseModel):
    head_ref: str = Field(min_length=1)
    base_ref: str = Field(min_length=1)


class RevisionOut(BaseModel):
    id: int
    number: int
    head_sha: str
    base_sha: str
    merge_base_sha: str
    created_at: datetime


class ReviewOut(BaseModel):
    id: int
    repo_id: int
    repo_path: str
    head_ref: str
    base_ref: str
    latest_revision: RevisionOut | None
    counts: dict[UnitState, int]
    total: int
    approved: int
    open_threads: int
    last_session_at: datetime | None


class ReviewDetailOut(ReviewOut):
    revisions: list[RevisionOut]


class RefreshIn(BaseModel):
    fetch: bool = False


class RefreshOut(BaseModel):
    revision: RevisionOut
    created: bool


class UnitOut(BaseModel):
    id: int
    revision_id: int
    path: str
    old_path: str | None
    kind: str
    qualified_name: str
    state: UnitState
    change_type: ChangeType
    base_changed: bool
    approval_id: str | None
    row_approvable: bool
    rows_total: int
    rows_approved: int
    base_start: int | None
    base_end: int | None
    head_start: int | None
    head_end: int | None
    binary: bool
    open_threads: int
    default_diff_mode: DiffMode


class DiffRowOut(BaseModel):
    change: LineChange
    old_index: int | None
    new_index: int | None
    old_line: int | None
    new_line: int | None
    text: str
    row_hash: str | None
    approved: bool
    selection_id: str | None


class DiffOut(BaseModel):
    unit_id: int
    mode: DiffMode
    available_modes: list[DiffMode]
    approved_text_unavailable: bool
    binary: bool
    unified: str
    rows: list[DiffRowOut]


class ApprovalIn(BaseModel):
    unit_id: int | None = None
    path: str | None = None
    head_range: LineRangeIn | None = None
    base_range: LineRangeIn | None = None

    @model_validator(mode="after")
    def check_target(self) -> "ApprovalIn":
        if (self.unit_id is None) == (self.path is None):
            raise ValueError("Give exactly one of unit_id or path")
        if self.path is not None and (self.head_range or self.base_range):
            raise ValueError("Line ranges need a unit_id")
        return self


class ApprovalOut(BaseModel):
    id: str
    path: str
    kind: str
    qualified_name: str
    head_hash: str | None
    created_at: datetime
    revoked_at: datetime | None


class RowApprovalOut(BaseModel):
    id: str
    selection_id: str
    side: str
    line_text: str


class ApprovalResultOut(BaseModel):
    approvals: list[ApprovalOut]
    row_approvals: list[RowApprovalOut]


class SessionOut(BaseModel):
    id: str
    revision_id: int
    completed_at: datetime
