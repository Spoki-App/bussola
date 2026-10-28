from dataclasses import dataclass, field

from rtool.errors import ConflictError, InvalidRequestError
from rtool.forge.base import ForgeAdapter, ForgeError, ForgeStatus, PullRequest
from rtool.git import GitRepo
from rtool.git.repo import DEFAULT_REMOTE
from rtool.review.hooks import REVISION_HOOKS
from rtool.review.revisions import RefreshResult, refresh_review
from rtool.storage.models import ForgeLink, Repo, Review, utcnow
from rtool.storage.repositories import Store

PULL_REF_PREFIX = "refs/rtool/pull/"
OPEN_STATE = "OPEN"


@dataclass(frozen=True)
class GitHubRemote:
    remote: str
    repository: str


@dataclass(frozen=True)
class PullRequestRow:
    pull: PullRequest
    review_id: int | None


@dataclass(frozen=True)
class PullRequestList:
    status: ForgeStatus
    repository: str | None
    pulls: list[PullRequestRow] = field(default_factory=list)


@dataclass(frozen=True)
class SyncResult:
    updated: int
    closed: int
    failed: list[str]


def pull_ref(number: int) -> str:
    return f"{PULL_REF_PREFIX}{number}"


def github_remote(adapter: ForgeAdapter, git_repo: GitRepo) -> GitHubRemote | None:
    remotes = git_repo.remotes()
    ordered = sorted(remotes, key=lambda name: name != DEFAULT_REMOTE)
    for remote in ordered:
        url = git_repo.remote_url(remote)
        repository = adapter.repository_for(url) if url else None
        if repository is not None:
            return GitHubRemote(remote, repository)
    return None


def list_pull_requests(store: Store, adapter: ForgeAdapter, git_repo: GitRepo, repo: Repo) -> PullRequestList:
    status = adapter.status()
    remote = github_remote(adapter, git_repo)
    if remote is None or not status.authenticated:
        return PullRequestList(status, remote.repository if remote else None)
    reviews = {link.pr_number: link.review_id for link in store.forge.links_for_repo(repo.id) if link.repository == remote.repository}
    pulls = [PullRequestRow(pull, reviews.get(pull.number)) for pull in adapter.open_pull_requests(remote.repository)]
    return PullRequestList(status, remote.repository, pulls)


def review_pull_request(store: Store, adapter: ForgeAdapter, git_repo: GitRepo, repo: Repo, number: int) -> Review:
    remote = _require_remote(adapter, git_repo)
    pull = adapter.pull_request(remote.repository, number)
    head_ref, base_ref = fetch_pull_request(git_repo, remote, pull)
    review = _review_for(store, repo, remote.repository, pull) or store.reviews.find_review(repo.id, head_ref, base_ref)
    if review is None:
        review = store.reviews.add_review(Review(repo_id=repo.id, head_ref=head_ref, base_ref=base_ref))
    review.head_ref, review.base_ref = head_ref, base_ref
    _save_link(store, review, adapter.provider, remote.repository, pull)
    refresh_review(store, review, git_repo, hooks=REVISION_HOOKS)
    return review


def sync_pull_requests(store: Store, adapter: ForgeAdapter, git_repo: GitRepo, repo: Repo) -> SyncResult:
    remote = _require_remote(adapter, git_repo)
    updated, closed = 0, 0
    failed: list[str] = []
    for link in store.forge.links_for_repo(repo.id):
        review = store.reviews.get_review(link.review_id)
        if review is None or link.repository != remote.repository:
            continue
        try:
            if sync_review(store, adapter, git_repo, review, link) is None:
                closed += 1
            else:
                updated += 1
        except (ForgeError, InvalidRequestError) as error:
            failed.append(f"#{link.pr_number}: {error}")
    return SyncResult(updated, closed, failed)


def sync_review(store: Store, adapter: ForgeAdapter, git_repo: GitRepo, review: Review, link: ForgeLink) -> RefreshResult | None:
    remote = _require_remote(adapter, git_repo)
    pull = adapter.pull_request(link.repository, link.pr_number)
    _save_link(store, review, adapter.provider, link.repository, pull)
    if pull.state != OPEN_STATE:
        return None
    review.head_ref, review.base_ref = fetch_pull_request(git_repo, remote, pull)
    return refresh_review(store, review, git_repo, hooks=REVISION_HOOKS)


def fetch_pull_request(git_repo: GitRepo, remote: GitHubRemote, pull: PullRequest) -> tuple[str, str]:
    if not git_repo.is_valid_branch_name(pull.base_ref):
        raise InvalidRequestError(f"Unexpected base branch name {pull.base_ref!r}")
    head_ref = pull_ref(pull.number)
    base_ref = f"{remote.remote}/{pull.base_ref}"
    git_repo.fetch_refspecs(remote.remote, [f"+refs/pull/{pull.number}/head:{head_ref}", f"+refs/heads/{pull.base_ref}:refs/remotes/{base_ref}"])
    return head_ref, base_ref


def _require_remote(adapter: ForgeAdapter, git_repo: GitRepo) -> GitHubRemote:
    remote = github_remote(adapter, git_repo)
    if remote is None:
        raise ConflictError("This repository has no GitHub remote")
    return remote


def _review_for(store: Store, repo: Repo, repository: str, pull: PullRequest) -> Review | None:
    link = next((link for link in store.forge.links_for_repo(repo.id) if link.repository == repository and link.pr_number == pull.number), None)
    return store.reviews.get_review(link.review_id) if link else None


def _save_link(store: Store, review: Review, provider: str, repository: str, pull: PullRequest) -> None:
    link = ForgeLink(
        review_id=review.id,
        provider=provider,
        repository=repository,
        pr_number=pull.number,
        title=pull.title,
        author=pull.author,
        url=pull.url,
        state=pull.state,
        synced_at=utcnow(),
    )
    store.forge.save_link(link)
