from collections.abc import Generator
from typing import Annotated

from fastapi import Depends, Request

from bussola.api.state import app_state
from bussola.errors import NotFoundError
from bussola.review.context import ReviewContext
from bussola.review.rows import Side
from bussola.storage.models import Repo, Reviewer, Revision, UnitSnapshot
from bussola.storage.repositories import Store


def get_store(request: Request) -> Generator[Store]:
    with app_state(request).database.session() as session:
        yield Store(session)


StoreDep = Annotated[Store, Depends(get_store)]


def current_reviewer(request: Request, store: StoreDep) -> Reviewer:
    identity = app_state(request).identity.current()
    reviewer = store.reviews.reviewer(identity.email, identity.name)
    store.commit()
    return reviewer


ReviewerDep = Annotated[Reviewer, Depends(current_reviewer)]


def review_context(review_id: int, store: StoreDep, reviewer: ReviewerDep) -> ReviewContext:
    review = store.reviews.get_review(review_id)
    if review is None:
        raise NotFoundError(f"Review {review_id} not found")
    return ReviewContext(store, review, reviewer)


ContextDep = Annotated[ReviewContext, Depends(review_context)]


def repo_of(context: ReviewContext) -> Repo:
    repo = context.store.reviews.get_repo(context.review.repo_id)
    if repo is None:
        raise NotFoundError("Repository not found")
    return repo


def get_repo(repo_id: int, store: StoreDep) -> Repo:
    repo = store.reviews.get_repo(repo_id)
    if repo is None:
        raise NotFoundError(f"Repository {repo_id} not found")
    return repo


RepoDep = Annotated[Repo, Depends(get_repo)]


def resolve_revision(context: ReviewContext, revision_id: int | None) -> Revision:
    revision = context.store.reviews.get_revision(revision_id) if revision_id is not None else context.store.reviews.latest_revision(context.review.id)
    if revision is None or revision.review_id != context.review.id:
        raise NotFoundError("Revision not found")
    return revision


def snapshot_of(context: ReviewContext, unit_id: int) -> UnitSnapshot:
    snapshot = context.store.reviews.get_snapshot(unit_id)
    revision = context.store.reviews.get_revision(snapshot.revision_id) if snapshot else None
    if snapshot is None or revision is None or revision.review_id != context.review.id:
        raise NotFoundError(f"Unit {unit_id} not found")
    return snapshot


def side_commit(revision: Revision, side: Side) -> str:
    return revision.merge_base_sha if side == Side.BASE else revision.head_sha


def side_path(snapshot: UnitSnapshot, side: Side) -> str:
    return snapshot.old_path or snapshot.path if side == Side.BASE else snapshot.path
