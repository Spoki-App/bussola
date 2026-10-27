from dataclasses import dataclass

from rtool.config import DEFAULT_BASE_CANDIDATES, RepoConfig
from rtool.git import GitRepo, InvalidRefError


@dataclass(frozen=True)
class ReviewCommits:
    head_sha: str
    base_sha: str
    merge_base_sha: str


class NoBaseBranchError(LookupError):
    def __init__(self) -> None:
        super().__init__(f"No base branch configured and none of {', '.join(DEFAULT_BASE_CANDIDATES)} exists")


def default_base_ref(repo: GitRepo, config: RepoConfig) -> str:
    candidates = (config.base_branch,) if config.base_branch else DEFAULT_BASE_CANDIDATES
    for candidate in candidates:
        try:
            repo.resolve_commit(candidate)
        except InvalidRefError:
            continue
        return candidate
    raise NoBaseBranchError


def resolve_review_commits(repo: GitRepo, head_ref: str, base_ref: str) -> ReviewCommits:
    head_sha = repo.resolve_commit(head_ref)
    base_sha = repo.resolve_commit(base_ref)
    return ReviewCommits(head_sha, base_sha, repo.merge_base(base_sha, head_sha))
