from dataclasses import dataclass
from enum import StrEnum

from bussola.forge.base import ForgeAdapter, ForgeError
from bussola.review.context import ReviewContext
from bussola.review.overview import unit_views
from bussola.review.states import DONE_STATES
from bussola.storage.models import ForgeLink, Revision

SHORT_SHA = 8


class ViewedStatus(StrEnum):
    MARKED = "marked"
    ALREADY_VIEWED = "already_viewed"
    FAILED = "failed"


@dataclass(frozen=True)
class ViewedFile:
    path: str
    status: ViewedStatus
    detail: str = ""


@dataclass(frozen=True)
class ViewedResult:
    files: list[ViewedFile]
    error: str | None = None


def fully_approved_paths(context: ReviewContext, revision: Revision) -> list[str]:
    approved: dict[str, bool] = {}
    for view in unit_views(context, revision, texts=False):
        path = view.snapshot.path
        approved[path] = approved.get(path, True) and view.status.state in DONE_STATES
    return sorted(path for path, done in approved.items() if done)


def mark_approved_files_viewed(context: ReviewContext, adapter: ForgeAdapter, link: ForgeLink, revision: Revision) -> ViewedResult:
    paths = fully_approved_paths(context, revision)
    if not paths:
        return ViewedResult([])
    try:
        views = adapter.file_views(link.repository, link.pr_number)
    except ForgeError as error:
        return ViewedResult([], str(error))
    if views.head_sha != revision.head_sha:
        pr_head, reviewed = views.head_sha[:SHORT_SHA], revision.head_sha[:SHORT_SHA]
        return ViewedResult([], f"The pull request head ({pr_head}) differs from the reviewed head ({reviewed}).")
    return ViewedResult([_mark(adapter, views.remote_id, views.viewed, path) for path in paths])


def _mark(adapter: ForgeAdapter, pull_id: str, viewed: dict[str, bool], path: str) -> ViewedFile:
    if path not in viewed:
        return ViewedFile(path, ViewedStatus.FAILED, "Not changed in the pull request")
    if viewed[path]:
        return ViewedFile(path, ViewedStatus.ALREADY_VIEWED)
    try:
        adapter.mark_file_viewed(pull_id, path)
    except ForgeError as error:
        return ViewedFile(path, ViewedStatus.FAILED, str(error))
    return ViewedFile(path, ViewedStatus.MARKED)
