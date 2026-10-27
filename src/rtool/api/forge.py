from dataclasses import asdict

from fastapi import APIRouter, Request

from rtool.api.deps import ContextDep, repo_of, resolve_revision
from rtool.api.schemas import ForgeLinkIn, ForgeLinkOut, ForgeOut, ForgeStatusOut, PublishIn, PublishOut, PublishOutcomeOut, PullRequestOut
from rtool.api.state import app_state
from rtool.forge.base import PullRequest
from rtool.forge.links import ForgeOverview, forge_overview, link_pull_request
from rtool.forge.publish import publish_comments
from rtool.review.context import ReviewContext
from rtool.review.repos import open_repo

router = APIRouter(tags=["forge"])


@router.get("/reviews/{review_id}/forge")
def get_forge(context: ContextDep, request: Request) -> ForgeOut:
    return _overview(context, request)


@router.put("/reviews/{review_id}/forge")
def put_forge(body: ForgeLinkIn, context: ContextDep, request: Request) -> ForgeOut:
    link_pull_request(context, app_state(request).forge, open_repo(repo_of(context)), body.pr_number)
    context.store.commit()
    return _overview(context, request)


@router.post("/reviews/{review_id}/forge/publish")
def publish(body: PublishIn, context: ContextDep, request: Request) -> PublishOut:
    result = publish_comments(context, app_state(request).forge, resolve_revision(context, None), draft=body.draft)
    context.store.commit()
    outcomes = [PublishOutcomeOut(comment_ids=list(item.comment_ids), status=item.status.value, detail=item.detail, url=item.url) for item in result.outcomes]
    return PublishOut(review_url=result.review_url, outcomes=outcomes)


def _overview(context: ReviewContext, request: Request) -> ForgeOut:
    revision = resolve_revision(context, None)
    overview: ForgeOverview = forge_overview(context, app_state(request).forge, open_repo(repo_of(context)), revision)
    link = overview.link
    pull = overview.pull_request
    return ForgeOut(
        status=ForgeStatusOut(**asdict(overview.status)),
        repository=overview.repository,
        link=ForgeLinkOut(provider=link.provider, repository=link.repository, pr_number=link.pr_number) if link else None,
        pull_request=_pull_out(pull) if pull else None,
        candidates=[_pull_out(item) for item in overview.candidates],
        pending_comments=overview.pending_comments,
        head_matches=pull.head_sha == revision.head_sha if pull else None,
        error=overview.error,
    )


def _pull_out(pull: PullRequest) -> PullRequestOut:
    return PullRequestOut(**asdict(pull))
