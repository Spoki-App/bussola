from dataclasses import dataclass, field

from rtool.errors import InvalidRequestError
from rtool.forge.base import ForgeAdapter, ForgeError, ForgeStatus, PullRequest
from rtool.forge.publish import pending_comment_count
from rtool.git import GitRepo
from rtool.git.repo import DEFAULT_REMOTE
from rtool.review.context import ReviewContext
from rtool.storage.models import ForgeLink, Revision


@dataclass(frozen=True)
class ForgeOverview:
    status: ForgeStatus
    repository: str | None
    link: ForgeLink | None
    pull_request: PullRequest | None
    pending_comments: int
    candidates: list[PullRequest] = field(default_factory=list)
    error: str | None = None


def review_repository(adapter: ForgeAdapter, git_repo: GitRepo, head_ref: str) -> str | None:
    remote = git_repo.upstream_remote(head_ref) or DEFAULT_REMOTE
    url = git_repo.remote_url(remote)
    return adapter.repository_for(url) if url else None


def branch_name(git_repo: GitRepo, ref: str) -> str:
    remote = next((name for name in git_repo.remotes() if ref.startswith(f"{name}/")), None)
    return ref.removeprefix(f"{remote}/") if remote else ref


def forge_overview(context: ReviewContext, adapter: ForgeAdapter, git_repo: GitRepo, revision: Revision) -> ForgeOverview:
    status = adapter.status()
    repository = review_repository(adapter, git_repo, context.review.head_ref)
    link = context.store.forge.link(context.review.id)
    pending = pending_comment_count(context, revision)
    if not status.authenticated or repository is None:
        return ForgeOverview(status, repository, link, None, pending)
    try:
        if link is not None:
            return ForgeOverview(status, repository, link, adapter.pull_request(link.repository, link.pr_number), pending)
        head, base = branch_name(git_repo, context.review.head_ref), branch_name(git_repo, context.review.base_ref)
        return ForgeOverview(status, repository, None, None, pending, adapter.find_pull_requests(repository, head, base))
    except ForgeError as error:
        return ForgeOverview(status, repository, link, None, pending, error=str(error))


def link_pull_request(context: ReviewContext, adapter: ForgeAdapter, git_repo: GitRepo, number: int) -> ForgeLink:
    repository = review_repository(adapter, git_repo, context.review.head_ref)
    if repository is None:
        raise InvalidRequestError("The review branch has no GitHub remote")
    pull = adapter.pull_request(repository, number)
    return context.store.forge.save_link(ForgeLink(review_id=context.review.id, provider=adapter.provider, repository=repository, pr_number=pull.number))
