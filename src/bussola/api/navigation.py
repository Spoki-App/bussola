from dataclasses import asdict
from pathlib import Path
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Query, Request

from bussola.api.deps import ContextDep, repo_of, resolve_revision
from bussola.api.schemas import (
    DocumentationOut,
    LibraryFileIn,
    LibraryFileOut,
    NavigationIn,
    NavigationIndexOut,
    NavigationOut,
    NavigationTargetOut,
    RevisionSideIn,
    ServerHintOut,
    SourceFileIn,
    SourceFileOut,
)
from bussola.api.state import app_state
from bussola.config import load_repo_config
from bussola.errors import InvalidRequestError, NotFoundError
from bussola.forge.links import review_repository
from bussola.navigation.external import is_library_file
from bussola.navigation.navigator import Click, Navigation, Navigator
from bussola.review.context import ReviewContext
from bussola.review.repos import open_repo
from bussola.review.rows import Side, side_commit, side_path
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
    ready = navigator(request).prepare(git_repo, side_commit(revision, query.side), load_repo_config(git_repo.root).ignore)
    return NavigationIndexOut(ready=ready)


@router.get("/reviews/{review_id}/navigation")
def navigate(context: ContextDep, request: Request, query: Annotated[NavigationIn, Query()]) -> NavigationOut:
    revision = resolve_revision(context, query.revision_id)
    git_repo = open_repo(repo_of(context))
    click = Click(query.path, query.line, query.column)
    found = navigator(request).navigate(git_repo, side_commit(revision, query.side), load_repo_config(git_repo.root).ignore, click)
    return _navigation_out(found, context, revision, query.side)


@router.get("/reviews/{review_id}/source")
def source_file(context: ContextDep, request: Request, query: Annotated[SourceFileIn, Query()]) -> SourceFileOut:
    revision = resolve_revision(context, query.revision_id)
    git_repo = open_repo(repo_of(context))
    commit = side_commit(revision, query.side)
    data = git_repo.file_at(commit, query.path)
    if data is None:
        raise NotFoundError(f"{query.path} does not exist on the {query.side.value} side")
    if len(data) > MAX_SOURCE_BYTES:
        raise InvalidRequestError(f"{query.path} is too large to show here")
    repository = review_repository(app_state(request).forge, git_repo, context.review.head_ref)
    url = GITHUB_BLOB_URL.format(repository=repository, commit=commit, path=quote(query.path)) if repository else None
    return SourceFileOut(path=query.path, side=query.side, commit=commit, text=data.decode(errors="replace"), url=url)


@router.get("/reviews/{review_id}/library-source")
def library_file(context: ContextDep, query: Annotated[LibraryFileIn, Query()]) -> LibraryFileOut:
    path = Path(query.path).resolve() if Path(query.path).is_absolute() else None
    if path is None or not is_library_file(path, open_repo(repo_of(context)).root):
        raise NotFoundError(f"{query.path} is not an installed library file of this repository")
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise InvalidRequestError(f"{query.path} is too large to show here")
    return LibraryFileOut(path=query.path, text=path.read_bytes().decode(errors="replace"), url=None)


def units_by_path(context: ReviewContext, revision: Revision, side: Side) -> dict[str, list[UnitSnapshot]]:
    units: dict[str, list[UnitSnapshot]] = {}
    for snapshot in context.store.reviews.snapshot_lines(revision.id):
        units.setdefault(side_path(snapshot, side), []).append(snapshot)
    return units


def unit_at(units: dict[str, list[UnitSnapshot]], side: Side, path: str, line: int) -> int | None:
    for snapshot in units.get(path, []):
        lines = snapshot.head_lines if side == Side.HEAD else snapshot.base_lines
        if line in lines:
            return snapshot.id
    return None


def _navigation_out(found: Navigation, context: ReviewContext, revision: Revision, side: Side) -> NavigationOut:
    units = units_by_path(context, revision, side) if found.targets else {}
    hint = ServerHintOut.model_validate(found.missing_server, from_attributes=True) if found.missing_server else None
    targets = [NavigationTargetOut(**asdict(target), side=side, unit_id=unit_at(units, side, target.path, target.line)) for target in found.targets]
    documentation = DocumentationOut.model_validate(asdict(found.documentation)) if found.documentation else None
    return NavigationOut(
        ready=found.ready, symbol=found.symbol, origin=found.origin, resolver=found.resolver, targets=targets, server_hint=hint, documentation=documentation
    )
