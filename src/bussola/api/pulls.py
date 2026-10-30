from pathlib import Path

from fastapi import APIRouter, Request, status

from bussola.api.deps import RepoDep, ReviewerDep, StoreDep
from bussola.api.schemas import PullRequestLinkIn, PullRequestListOut, PullRequestRowOut, PullSyncOut, ReviewDetailOut
from bussola.api.state import app_state
from bussola.api.views import forge_status_out, pull_request_out, review_detail_out
from bussola.directories import find_repositories
from bussola.forge.pulls import ForgeSession, find_repo_for, list_pull_requests, parse_pull_request_url, review_pull_request
from bussola.forge.review_sync import sync_pull_requests
from bussola.review.context import ReviewContext
from bussola.review.repos import open_repo

router = APIRouter(tags=["pull requests"])


@router.get("/repos/{repo_id}/pulls")
def get_pull_requests(repo: RepoDep, store: StoreDep, request: Request) -> PullRequestListOut:
    listing = list_pull_requests(store, app_state(request).forge, open_repo(repo), repo)
    rows = [PullRequestRowOut(pull=pull_request_out(row.pull), review_id=row.review_id) for row in listing.pulls]
    return PullRequestListOut(status=forge_status_out(listing.status), repository=listing.repository, pulls=rows)


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


@router.post("/pulls/open", status_code=status.HTTP_201_CREATED)
def open_pull_request_link(body: PullRequestLinkIn, store: StoreDep, reviewer: ReviewerDep, request: Request) -> ReviewDetailOut:
    address = parse_pull_request_url(body.url)
    adapter = app_state(request).forge
    repo = find_repo_for(store, adapter, address.repository, _repositories_under_home)
    review = review_pull_request(ForgeSession(store, adapter, open_repo(repo), reviewer), repo, address.number, address.repository)
    store.commit()
    return review_detail_out(ReviewContext(store, review, reviewer), repo)


def _repositories_under_home() -> list[Path]:
    return [Path(found.path) for found in find_repositories().repositories]
