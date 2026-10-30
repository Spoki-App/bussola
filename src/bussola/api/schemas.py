from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, model_validator

from bussola.review.diffs import DiffMode
from bussola.review.rows import LineChange, Side
from bussola.review.scope import ChangeType
from bussola.review.states import ApprovalAction, UnitState
from bussola.review.thread_types import ThreadScope, ThreadStatus

MAX_THREAD_LINES = 500

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


class ReviewPullOut(BaseModel):
    number: int
    title: str | None
    url: str | None
    author: str | None
    state: str | None
    description: str | None = None


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
    total_threads: int
    last_session_at: datetime | None
    pull_request: ReviewPullOut | None = None
    pull_request_review: bool = False


class ReviewDetailOut(ReviewOut):
    unsent_comments: int = 0


class RefreshIn(BaseModel):
    fetch: bool = False


class RefreshOut(BaseModel):
    revision: RevisionOut
    created: bool
    warning: str | None = None


class UnitOut(BaseModel):
    id: int
    revision_id: int
    path: str
    old_path: str | None
    module: str | None
    kind: str
    qualified_name: str
    state: UnitState
    change_type: ChangeType
    base_changed: bool
    approval_id: str | None
    row_approvable: bool
    rows_total: int
    rows_approved: int
    binary: bool
    image: bool
    todo: bool
    action: ApprovalAction
    open_threads: int


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
    placeholder: bool


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


class ThreadIn(BaseModel):
    scope: ThreadScope
    body: str
    unit_id: int | None = None
    path: str | None = None
    side: Side = Side.HEAD
    line_offset: int | None = None
    line_count: int = Field(default=1, ge=1, le=MAX_THREAD_LINES)


class ThreadPatch(BaseModel):
    status: ThreadStatus


class CommentIn(BaseModel):
    body: str


class CommentOut(BaseModel):
    id: str
    thread_id: str
    author: ReviewerOut
    body: str
    created_at: datetime
    edited_at: datetime | None
    deleted: bool
    mine: bool
    remote_url: str | None = None


class ThreadAnchorOut(BaseModel):
    revision_id: int
    line_offset: int | None
    outdated: bool
    unit_id: int | None
    file_line: int | None
    end_file_line: int | None


class ThreadOut(BaseModel):
    id: str
    scope: ThreadScope
    path: str | None
    module: str | None
    kind: str | None
    qualified_name: str | None
    side: Side | None
    status: ThreadStatus
    resolvable: bool
    created_by: ReviewerOut
    created_at: datetime
    line_text: str | None
    line_count: int
    context_before: list[str]
    context_after: list[str]
    anchor: ThreadAnchorOut | None
    comments: list[CommentOut]
    can_delete: bool


class ThreadDeletedOut(BaseModel):
    id: str
    deleted: bool


class ForgeStatusOut(BaseModel):
    available: bool
    authenticated: bool
    message: str


class PullRequestOut(BaseModel):
    number: int
    title: str
    url: str
    head_sha: str
    head_ref: str
    base_ref: str
    author: str
    state: str
    is_draft: bool
    comment_count: int
    unresolved_threads: int
    body: str


class ForgeLinkOut(BaseModel):
    provider: str
    repository: str
    pr_number: int


class ForgeOut(BaseModel):
    status: ForgeStatusOut
    repository: str | None
    link: ForgeLinkOut | None
    pull_request: PullRequestOut | None
    candidates: list[PullRequestOut]
    head_matches: bool | None
    error: str | None


class ForgeLinkIn(BaseModel):
    pr_number: int = Field(gt=0)


class PublishOutcomeOut(BaseModel):
    comment_ids: list[str]
    status: str
    detail: str
    url: str | None


class PublishOut(BaseModel):
    review_url: str | None
    outcomes: list[PublishOutcomeOut]


class SyncOut(BaseModel):
    refresh: RefreshOut
    published: PublishOut | None
    publish_error: str | None
    unsent_comments: int


class DirectoryEntryOut(BaseModel):
    name: str
    path: str
    is_repo: bool


class DirectoryListingOut(BaseModel):
    path: str
    parent: str | None
    home: str
    is_repo: bool
    entries: list[DirectoryEntryOut]
    truncated: bool


class FoundRepositoryOut(BaseModel):
    name: str
    path: str
    registered: bool


class RepositoryScanOut(BaseModel):
    root: str
    repositories: list[FoundRepositoryOut]
    truncated: bool


class PullRequestRowOut(BaseModel):
    pull: PullRequestOut
    review_id: int | None


class PullRequestListOut(BaseModel):
    status: ForgeStatusOut
    repository: str | None
    pulls: list[PullRequestRowOut]


class ConversationSyncOut(BaseModel):
    changes: int
    new_commits: bool
    state: str


class PullRequestLinkIn(BaseModel):
    url: str = Field(max_length=2048)


class PullSyncOut(BaseModel):
    updated: int
    closed: int
    failed: list[str]
