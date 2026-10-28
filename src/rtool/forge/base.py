from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol


class ForgeError(Exception):
    pass


class DiffSide(StrEnum):
    RIGHT = "RIGHT"
    LEFT = "LEFT"


@dataclass(frozen=True)
class ForgeStatus:
    available: bool
    authenticated: bool
    message: str


@dataclass(frozen=True)
class PullRequest:
    number: int
    title: str
    url: str
    head_sha: str
    head_ref: str
    base_ref: str
    author: str = ""
    state: str = "OPEN"
    is_draft: bool = False
    updated_at: str = ""
    comment_count: int = 0
    unresolved_threads: int = 0
    body: str = ""


@dataclass(frozen=True)
class LineRanges:
    right: tuple[tuple[int, int], ...] = ()
    left: tuple[tuple[int, int], ...] = ()

    def contains(self, side: DiffSide, line: int, end_line: int | None = None) -> bool:
        ranges = self.right if side == DiffSide.RIGHT else self.left
        last = line if end_line is None else end_line
        return any(start <= line and last <= end for start, end in ranges)


@dataclass(frozen=True)
class InlineComment:
    path: str
    line: int
    side: DiffSide
    body: str
    start_line: int | None = None


@dataclass(frozen=True)
class ReviewSubmission:
    commit_id: str
    body: str
    comments: list[InlineComment] = field(default_factory=list)


@dataclass(frozen=True)
class RemoteComment:
    remote_id: str | None
    url: str | None


@dataclass(frozen=True)
class SubmittedReview:
    url: str | None
    comments: list[RemoteComment]
    remote_id: str | None = None


@dataclass(frozen=True)
class RemoteNote:
    remote_id: str
    author: str
    body: str
    created_at: str
    url: str


@dataclass(frozen=True)
class RemoteThread:
    path: str
    line: int | None
    start_line: int | None
    side: DiffSide
    resolved: bool
    comments: list[RemoteNote]
    remote_id: str = ""


@dataclass(frozen=True)
class Conversation:
    viewer: str
    head_sha: str
    notes: list[RemoteNote]
    threads: list[RemoteThread]


@dataclass(frozen=True)
class Asset:
    content_type: str
    data: bytes


class ForgeAdapter(Protocol):
    provider: str

    def status(self) -> ForgeStatus: ...
    def repository_for(self, remote_url: str) -> str | None: ...
    def find_pull_requests(self, repository: str, head_branch: str, base_branch: str) -> list[PullRequest]: ...
    def open_pull_requests(self, repository: str) -> list[PullRequest]: ...
    def pull_request(self, repository: str, number: int) -> PullRequest: ...
    def diff_ranges(self, repository: str, number: int) -> dict[str, LineRanges]: ...
    def submit_review(self, repository: str, number: int, submission: ReviewSubmission) -> SubmittedReview: ...
    def create_file_comment(self, repository: str, number: int, commit_id: str, path: str, body: str) -> RemoteComment: ...
    def reply(self, repository: str, number: int, remote_id: str, body: str) -> RemoteComment: ...
    def update_comment(self, repository: str, remote_id: str, body: str) -> None: ...
    def pull_request_conversation(self, repository: str, number: int) -> Conversation: ...
    def set_thread_resolved(self, thread_id: str, resolved: bool) -> None: ...
    def download_asset(self, url: str) -> Asset: ...
