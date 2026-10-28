import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from rtool.errors import ConflictError, InvalidRequestError, NotFoundError
from rtool.forge.base import ForgeAdapter, ForgeError, ForgeStatus, PullRequest
from rtool.forge.conversation import import_conversation
from rtool.git import GitError, GitRepo
from rtool.git.repo import DEFAULT_REMOTE
from rtool.review.context import ReviewContext
from rtool.review.hooks import REVISION_HOOKS
from rtool.review.repos import open_repo, register_repo
from rtool.review.revisions import RefreshResult, refresh_review
from rtool.storage.models import ForgeLink, Repo, Review, Reviewer, utcnow
from rtool.storage.repositories import Store

PULL_REF_PREFIX = "refs/rtool/pull/"
OPEN_STATE = "OPEN"
PULL_URL = re.compile(r"^(?:https?://)?(?:www\.)?github\.com/(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)/pull/(?P<number>\d+)(?:[/?#].*)?$")


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


@dataclass(frozen=True)
class ConversationSync:
    changes: int
    new_commits: bool
    state: str


@dataclass(frozen=True)
class PullRequestAddress:
    repository: str
    number: int


def parse_pull_request_url(url: str) -> PullRequestAddress:
    match = PULL_URL.match(url.strip())
    if match is None:
        raise InvalidRequestError("Not a GitHub pull request link. Expected https://github.com/<owner>/<repository>/pull/<number>.")
    return PullRequestAddress(match["repository"], int(match["number"]))


def find_repo_for(store: Store, adapter: ForgeAdapter, repository: str, candidates: Callable[[], Iterable[Path]]) -> Repo:
    for repo in store.reviews.list_repos():
        if Path(repo.path).is_dir() and _has_remote(adapter, open_repo(repo), repository):
            return repo
    for path in candidates():
        try:
            matches = _has_remote(adapter, GitRepo(path), repository)
        except GitError:
            continue
        if matches:
            return register_repo(store, path)
    raise NotFoundError(f"No local clone of github.com/{repository} was found. Add its folder as a repository first.")


def _has_remote(adapter: ForgeAdapter, git_repo: GitRepo, repository: str) -> bool:
    return github_remote(adapter, git_repo, repository) is not None


def pull_ref(number: int) -> str:
    return f"{PULL_REF_PREFIX}{number}"


def github_remote(adapter: ForgeAdapter, git_repo: GitRepo, repository: str | None = None) -> GitHubRemote | None:
    remotes = git_repo.remotes()
    ordered = sorted(remotes, key=lambda name: name != DEFAULT_REMOTE)
    for remote in ordered:
        url = git_repo.remote_url(remote)
        found = adapter.repository_for(url) if url else None
        if found is not None and (repository is None or found.lower() == repository.lower()):
            return GitHubRemote(remote, found)
    return None


def list_pull_requests(store: Store, adapter: ForgeAdapter, git_repo: GitRepo, repo: Repo) -> PullRequestList:
    status = adapter.status()
    remote = github_remote(adapter, git_repo)
    if remote is None or not status.authenticated:
        return PullRequestList(status, remote.repository if remote else None)
    reviews = {link.pr_number: link.review_id for link in store.forge.links_for_repo(repo.id) if link.repository == remote.repository}
    pulls = [PullRequestRow(pull, reviews.get(pull.number)) for pull in adapter.open_pull_requests(remote.repository)]
    return PullRequestList(status, remote.repository, pulls)


@dataclass(frozen=True)
class ForgeSession:
    store: Store
    adapter: ForgeAdapter
    git_repo: GitRepo
    reviewer: Reviewer


def review_pull_request(session: ForgeSession, repo: Repo, number: int, repository: str | None = None) -> Review:
    store, adapter, git_repo = session.store, session.adapter, session.git_repo
    remote = _require_remote(adapter, git_repo, repository)
    pull = adapter.pull_request(remote.repository, number)
    head_ref, base_ref = fetch_pull_request(git_repo, remote, pull)
    review = _review_for(store, repo, remote.repository, pull) or store.reviews.find_review(repo.id, head_ref, base_ref)
    if review is None:
        review = store.reviews.add_review(Review(repo_id=repo.id, head_ref=head_ref, base_ref=base_ref))
    review.head_ref, review.base_ref = head_ref, base_ref
    link = _save_link(store, review, adapter.provider, remote.repository, pull)
    result = refresh_review(store, review, git_repo, hooks=REVISION_HOOKS)
    import_conversation(ReviewContext(store, review, session.reviewer), adapter, link, result.revision)
    return review


def sync_pull_requests(session: ForgeSession, repo: Repo) -> SyncResult:
    remote = _require_remote(session.adapter, session.git_repo)
    updated, closed = 0, 0
    failed: list[str] = []
    for link in session.store.forge.links_for_repo(repo.id):
        review = session.store.reviews.get_review(link.review_id)
        if review is None or link.repository != remote.repository:
            continue
        try:
            if sync_review(session, review, link) is None:
                closed += 1
            else:
                updated += 1
        except (ForgeError, InvalidRequestError) as error:
            failed.append(f"#{link.pr_number}: {error}")
    return SyncResult(updated, closed, failed)


def sync_review(session: ForgeSession, review: Review, link: ForgeLink) -> RefreshResult | None:
    store, adapter, git_repo = session.store, session.adapter, session.git_repo
    remote = _require_remote(adapter, git_repo, link.repository)
    pull = adapter.pull_request(link.repository, link.pr_number)
    _save_link(store, review, adapter.provider, link.repository, pull)
    if pull.state != OPEN_STATE:
        return None
    review.head_ref, review.base_ref = fetch_pull_request(git_repo, remote, pull)
    result = refresh_review(store, review, git_repo, hooks=REVISION_HOOKS)
    import_conversation(ReviewContext(store, review, session.reviewer), adapter, link, result.revision)
    return result


def sync_conversation(context: ReviewContext, adapter: ForgeAdapter, link: ForgeLink) -> ConversationSync:
    revision = context.store.reviews.latest_revision(context.review.id)
    if revision is None:
        raise ConflictError("This review has no revision yet")
    pull = adapter.pull_request(link.repository, link.pr_number)
    _save_link(context.store, context.review, adapter.provider, link.repository, pull)
    changes = import_conversation(context, adapter, link, revision)
    return ConversationSync(changes, pull.head_sha != revision.head_sha, pull.state)


def fetch_pull_request(git_repo: GitRepo, remote: GitHubRemote, pull: PullRequest) -> tuple[str, str]:
    if not git_repo.is_valid_branch_name(pull.base_ref):
        raise InvalidRequestError(f"Unexpected base branch name {pull.base_ref!r}")
    head_ref = pull_ref(pull.number)
    base_ref = f"{remote.remote}/{pull.base_ref}"
    git_repo.fetch_refspecs(remote.remote, [f"+refs/pull/{pull.number}/head:{head_ref}", f"+refs/heads/{pull.base_ref}:refs/remotes/{base_ref}"])
    return head_ref, base_ref


def _require_remote(adapter: ForgeAdapter, git_repo: GitRepo, repository: str | None = None) -> GitHubRemote:
    remote = github_remote(adapter, git_repo, repository)
    if remote is None:
        raise ConflictError(f"This repository has no GitHub remote for {repository}" if repository else "This repository has no GitHub remote")
    return remote


def _review_for(store: Store, repo: Repo, repository: str, pull: PullRequest) -> Review | None:
    link = next((link for link in store.forge.links_for_repo(repo.id) if link.repository == repository and link.pr_number == pull.number), None)
    return store.reviews.get_review(link.review_id) if link else None


def _save_link(store: Store, review: Review, provider: str, repository: str, pull: PullRequest) -> ForgeLink:
    link = ForgeLink(
        review_id=review.id,
        provider=provider,
        repository=repository,
        pr_number=pull.number,
        title=pull.title,
        author=pull.author,
        url=pull.url,
        state=pull.state,
        description=pull.body,
        synced_at=utcnow(),
    )
    return store.forge.save_link(link)
