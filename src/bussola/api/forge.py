from collections import OrderedDict
from dataclasses import asdict

from fastapi import APIRouter, Request, Response

from bussola.api.deps import ContextDep, repo_of, resolve_revision
from bussola.api.images import image_response
from bussola.api.schemas import (
    ConversationSyncOut,
    ForgeLinkIn,
    ForgeLinkOut,
    ForgeOut,
    MergeIn,
    MergeOptionsOut,
    MergeOut,
    ReviewSubmitIn,
    ReviewSubmitOut,
)
from bussola.api.state import app_state
from bussola.api.views import forge_status_out, merge_options_out, publish_out, pull_request_out
from bussola.forge.base import Asset, MergeRequest
from bussola.forge.links import ForgeOverview, forge_overview, link_pull_request
from bussola.forge.merge import merge_pull_request, review_merge_options
from bussola.forge.publish import ReviewVerdict, pending_comment_count, publish_comments, require_link
from bussola.forge.pulls import sync_conversation
from bussola.review.context import ReviewContext
from bussola.review.repos import open_repo

router = APIRouter(tags=["forge"])

ASSET_CACHE_SIZE = 64
_assets: OrderedDict[str, Asset] = OrderedDict()


@router.get("/forge/asset")
def forge_asset(url: str, request: Request) -> Response:
    asset = _assets.get(url) or app_state(request).forge.download_asset(url)
    _assets[url] = asset
    _assets.move_to_end(url)
    while len(_assets) > ASSET_CACHE_SIZE:
        _assets.popitem(last=False)
    return image_response(asset.data, asset.content_type)


@router.get("/reviews/{review_id}/forge")
def get_forge(context: ContextDep, request: Request) -> ForgeOut:
    return _overview(context, request)


@router.put("/reviews/{review_id}/forge")
def put_forge(body: ForgeLinkIn, context: ContextDep, request: Request) -> ForgeOut:
    link_pull_request(context, app_state(request).forge, open_repo(repo_of(context)), body.pr_number)
    context.store.commit()
    return _overview(context, request)


@router.post("/reviews/{review_id}/forge/sync")
def sync(context: ContextDep, request: Request) -> ConversationSyncOut:
    result = sync_conversation(context, app_state(request).forge, require_link(context))
    context.store.commit()
    return ConversationSyncOut(changes=result.changes, new_commits=result.new_commits, state=result.state)


@router.post("/reviews/{review_id}/forge/review")
def submit_review(body: ReviewSubmitIn, context: ContextDep, request: Request) -> ReviewSubmitOut:
    revision = resolve_revision(context, None)
    result = publish_comments(context, app_state(request).forge, revision, ReviewVerdict(body.event, body.body))
    context.store.commit()
    return ReviewSubmitOut(event=body.event, published=publish_out(result), unsent_comments=pending_comment_count(context, revision))


@router.get("/reviews/{review_id}/forge/merge")
def get_merge_options(context: ContextDep, request: Request) -> MergeOptionsOut:
    return merge_options_out(review_merge_options(context, app_state(request).forge, require_link(context)))


@router.post("/reviews/{review_id}/forge/merge")
def merge(body: MergeIn, context: ContextDep, request: Request) -> MergeOut:
    merge_request = MergeRequest(body.method, body.head_sha, body.title, body.message)
    outcome = merge_pull_request(context, app_state(request).forge, require_link(context), merge_request, body.delete_branch)
    context.store.commit()
    return MergeOut(**asdict(outcome))


def _overview(context: ReviewContext, request: Request) -> ForgeOut:
    revision = resolve_revision(context, None)
    overview: ForgeOverview = forge_overview(context, app_state(request).forge, open_repo(repo_of(context)))
    link = overview.link
    pull = overview.pull_request
    return ForgeOut(
        status=forge_status_out(overview.status),
        repository=overview.repository,
        link=ForgeLinkOut(provider=link.provider, repository=link.repository, pr_number=link.pr_number) if link else None,
        pull_request=pull_request_out(pull) if pull else None,
        candidates=[pull_request_out(item) for item in overview.candidates],
        head_matches=pull.head_sha == revision.head_sha if pull else None,
        error=overview.error,
        viewer=overview.viewer,
    )
