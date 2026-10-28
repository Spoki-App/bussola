from dataclasses import asdict

from fastapi import APIRouter, Request, status

from rtool.api.deps import RepoDep, ReviewerDep, StoreDep
from rtool.api.schemas import ForgeStatusOut, PullRequestListOut, PullRequestOut, PullRequestRowOut, PullSyncOut, ReviewDetailOut
from rtool.api.state import app_state
from rtool.api.views import review_detail_out
from rtool.forge.pulls import ForgeSession, list_pull_requests, review_pull_request, sync_pull_requests
from rtool.review.context import ReviewContext
from rtool.review.repos import open_repo

router = APIRouter(tags=["pull requests"])


@router.get("/repos/{repo_id}/pulls")
def get_pull_requests(repo: RepoDep, store: StoreDep, request: Request) -> PullRequestListOut:
    listing = list_pull_requests(store, app_state(request).forge, open_repo(repo), repo)
    rows = [PullRequestRowOut(pull=PullRequestOut(**asdict(row.pull)), review_id=row.review_id) for row in listing.pulls]
    return PullRequestListOut(status=ForgeStatusOut(**asdict(listing.status)), repository=listing.repository, pulls=rows)


@router.post("/repos/{repo_id}/pulls/{number}/review", status_code=status.HTTP_201_CREATED)
def start_pull_request_review(number: int, repo: RepoDep, store: StoreDep, reviewer: ReviewerDep, request: Request) -> ReviewDetailOut:
    review = review_pull_request(ForgeSession(store, app_state(request).forge, open_repo(repo), reviewer), repo, number)
    store.commit()
    return review_detail_out(ReviewContext(store, review, reviewer), repo)


@router.post("/repos/{repo_id}/pulls/sync")
def sync_pulls(repo: RepoDep, store: StoreDep, reviewer: ReviewerDep, request: Request) -> PullSyncOut:
    result = sync_pull_requests(ForgeSession(store, app_state(request).forge, open_repo(repo), reviewer), repo)
    store.commit()
    return PullSyncOut(updated=result.updated, closed=result.closed, failed=result.failed)
