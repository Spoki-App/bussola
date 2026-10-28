from collections import OrderedDict

from fastapi import APIRouter, Request, Response

from rtool.api.deps import ContextDep, repo_of, resolve_revision
from rtool.api.images import image_response
from rtool.api.schemas import (
    ConversationSyncOut,
    ForgeLinkIn,
    ForgeLinkOut,
    ForgeOut,
)
from rtool.api.state import app_state
from rtool.api.views import forge_status_out, pull_request_out
from rtool.forge.base import Asset
from rtool.forge.links import ForgeOverview, forge_overview, link_pull_request
from rtool.forge.publish import require_link
from rtool.forge.pulls import sync_conversation
from rtool.review.context import ReviewContext
from rtool.review.repos import open_repo

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
    )
