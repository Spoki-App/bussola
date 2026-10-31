from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Query, Request

from bussola.api.deps import ContextDep, repo_of, resolve_revision
from bussola.api.schemas import NavigationIn, NavigationIndexOut, NavigationOut, NavigationTargetOut, RevisionSideIn, ServerHintOut, SourceFileIn, SourceFileOut
from bussola.api.state import app_state
from bussola.config import load_repo_config
from bussola.errors import InvalidRequestError, NotFoundError
from bussola.forge.links import review_repository
from bussola.navigation.navigator import Click, Navigation, Navigator, Target
from bussola.review.context import ReviewContext
from bussola.review.repos import open_repo
from bussola.review.rows import Side
from bussola.storage.models import Revision, UnitSnapshot

MAX_SOURCE_BYTES = 2_000_000
GITHUB_BLOB_URL = "https://github.com/{repository}/blob/{commit}/{path}"

router = APIRouter(tags=["navigation"])


def navigator(request: Request) -> Navigator:
    return app_state(request).navigator


@router.post("/reviews/{review_id}/navigation/index")
def prepare_index(context: ContextDep, request: Request, query: Annotated[RevisionSideIn, Query()]) -> NavigationIndexOut:
    revision = resolve_revision(context, query.revision_id)
    git_repo = open_repo(repo_of(context))
    ready = navigator(request).prepare(git_repo, _commit(revision, query.side), load_repo_config(git_repo.root).ignore)
    return NavigationIndexOut(ready=ready)


@router.get("/reviews/{review_id}/navigation")
def navigate(context: ContextDep, request: Request, query: Annotated[NavigationIn, Query()]) -> NavigationOut:
    revision = resolve_revision(context, query.revision_id)
    git_repo = open_repo(repo_of(context))
    click = Click(query.path, query.line, query.column)
    found = navigator(request).navigate(git_repo, _commit(revision, query.side), load_repo_config(git_repo.root).ignore, click)
    return _navigation_out(found, query.side, _units_by_path(context, revision, query.side))


@router.get("/reviews/{review_id}/source")
def source_file(context: ContextDep, request: Request, query: Annotated[SourceFileIn, Query()]) -> SourceFileOut:
    revision = resolve_revision(context, query.revision_id)
    git_repo = open_repo(repo_of(context))
    commit = _commit(revision, query.side)
    data = git_repo.file_at(commit, query.path)
    if data is None:
        raise NotFoundError(f"{query.path} does not exist on the {query.side.value} side")
    if len(data) > MAX_SOURCE_BYTES:
        raise InvalidRequestError(f"{query.path} is too large to show here")
    repository = review_repository(app_state(request).forge, git_repo, context.review.head_ref)
    url = GITHUB_BLOB_URL.format(repository=repository, commit=commit, path=quote(query.path)) if repository else None
    return SourceFileOut(path=query.path, side=query.side, commit=commit, text=data.decode(errors="replace"), url=url)


def _commit(revision: Revision, side: Side) -> str:
    return revision.head_sha if side == Side.HEAD else revision.merge_base_sha


def _units_by_path(context: ReviewContext, revision: Revision, side: Side) -> dict[str, list[UnitSnapshot]]:
    units: dict[str, list[UnitSnapshot]] = {}
    for snapshot in context.store.reviews.snapshots(revision.id, texts=False):
        path = snapshot.path if side == Side.HEAD else snapshot.old_path or snapshot.path
        units.setdefault(path, []).append(snapshot)
    return units


def _unit_at(units: dict[str, list[UnitSnapshot]], side: Side, target: Target) -> int | None:
    for snapshot in units.get(target.path, []):
        lines = snapshot.head_lines if side == Side.HEAD else snapshot.base_lines
        if target.line in lines:
            return snapshot.id
    return None


def _navigation_out(found: Navigation, side: Side, units: dict[str, list[UnitSnapshot]]) -> NavigationOut:
    hint = (
        ServerHintOut(family=found.missing_server.family, language=found.missing_server.language, install=found.missing_server.install)
        if found.missing_server
        else None
    )
    targets = [
        NavigationTargetOut(
            role=target.role,
            path=target.path,
            line=target.line,
            column=target.column,
            preview=target.preview,
            side=side,
            unit_id=_unit_at(units, side, target),
        )
        for target in found.targets
    ]
    return NavigationOut(ready=found.ready, symbol=found.symbol, origin=found.origin, resolver=found.resolver, targets=targets, server_hint=hint)
