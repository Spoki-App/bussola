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


@dataclass(frozen=True)
class LineRanges:
    right: tuple[tuple[int, int], ...] = ()
    left: tuple[tuple[int, int], ...] = ()

    def contains(self, side: DiffSide, line: int) -> bool:
        ranges = self.right if side == DiffSide.RIGHT else self.left
        return any(start <= line <= end for start, end in ranges)


@dataclass(frozen=True)
class InlineComment:
    path: str
    line: int
    side: DiffSide
    body: str


@dataclass(frozen=True)
class ReviewSubmission:
    commit_id: str
    body: str
    comments: list[InlineComment] = field(default_factory=list)
    draft: bool = False


@dataclass(frozen=True)
class RemoteComment:
    remote_id: str | None
    url: str | None


@dataclass(frozen=True)
class SubmittedReview:
    url: str | None
    comments: list[RemoteComment]


class ForgeAdapter(Protocol):
    provider: str

    def status(self) -> ForgeStatus: ...
    def repository_for(self, remote_url: str) -> str | None: ...
    def find_pull_requests(self, repository: str, head_branch: str, base_branch: str) -> list[PullRequest]: ...
    def pull_request(self, repository: str, number: int) -> PullRequest: ...
    def diff_ranges(self, repository: str, number: int) -> dict[str, LineRanges]: ...
    def submit_review(self, repository: str, number: int, submission: ReviewSubmission) -> SubmittedReview: ...
    def create_file_comment(self, repository: str, number: int, commit_id: str, path: str, body: str) -> RemoteComment: ...
    def reply(self, repository: str, number: int, remote_id: str, body: str) -> RemoteComment: ...
    def update_comment(self, repository: str, remote_id: str, body: str) -> None: ...
