from pathlib import Path

from fastapi import APIRouter, status

from rtool.api.deps import RepoDep, ReviewerDep, StoreDep
from rtool.api.schemas import RefsOut, RepoIn, RepoOut, ReviewDetailOut, ReviewIn, ReviewOut
from rtool.api.views import repo_out, review_detail_out, review_out
from rtool.config import load_repo_config
from rtool.review.context import ReviewContext
from rtool.review.hooks import REVISION_HOOKS
from rtool.review.refs import NoBaseBranchError, default_base_ref
from rtool.review.repos import open_repo, register_repo
from rtool.review.revisions import refresh_review
from rtool.storage.models import Review

router = APIRouter(tags=["repos"])


@router.get("/repos")
def list_repos(store: StoreDep) -> list[RepoOut]:
    return [repo_out(repo) for repo in store.reviews.list_repos()]


@router.post("/repos", status_code=status.HTTP_201_CREATED)
def add_repo(body: RepoIn, store: StoreDep) -> RepoOut:
    repo = register_repo(store, Path(body.path))
    store.commit()
    return repo_out(repo)


@router.get("/repos/{repo_id}/refs")
def list_refs(repo: RepoDep) -> RefsOut:
    git_repo = open_repo(repo)
    local, remote = git_repo.branches()
    try:
        default_base = default_base_ref(git_repo, load_repo_config(git_repo.root))
    except NoBaseBranchError:
        default_base = None
    return RefsOut(local=local, remote=remote, default_base=default_base)


@router.get("/repos/{repo_id}/reviews")
def list_reviews(repo: RepoDep, store: StoreDep, reviewer: ReviewerDep) -> list[ReviewOut]:
    return [review_out(ReviewContext(store, review, reviewer), repo) for review in store.reviews.list_reviews(repo.id)]


@router.post("/repos/{repo_id}/reviews", status_code=status.HTTP_201_CREATED)
def create_review(body: ReviewIn, repo: RepoDep, store: StoreDep, reviewer: ReviewerDep) -> ReviewDetailOut:
    git_repo = open_repo(repo)
    git_repo.resolve_commit(body.head_ref)
    git_repo.resolve_commit(body.base_ref)
    review = store.reviews.find_review(repo.id, body.head_ref, body.base_ref)
    if review is None:
        review = store.reviews.add_review(Review(repo_id=repo.id, head_ref=body.head_ref, base_ref=body.base_ref))
    context = ReviewContext(store, review, reviewer)
    refresh_review(store, review, git_repo, hooks=REVISION_HOOKS)
    store.commit()
    return review_detail_out(context, repo)
