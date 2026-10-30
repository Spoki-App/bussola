from dataclasses import dataclass, field

from bussola.forge.base import ForgeAdapter, ForgeError
from bussola.forge.heads import head_mismatch
from bussola.review.context import ReviewContext
from bussola.review.overview import complete_paths, unit_views
from bussola.storage.models import ForgeLink, Revision

BATCH_SIZE = 50


@dataclass(frozen=True)
class ViewedResult:
    marked: list[str] = field(default_factory=list[str])
    failed: dict[str, str] = field(default_factory=dict[str, str])
    error: str | None = None


@dataclass(frozen=True)
class _Changed:
    done: list[str]
    failed: dict[str, str]
    error: str | None = None


def mark_approved_files_viewed(context: ReviewContext, adapter: ForgeAdapter, link: ForgeLink, revision: Revision) -> ViewedResult:
    paths = complete_paths(unit_views(context, revision, texts=False))
    if not paths:
        return ViewedResult()
    try:
        views = adapter.file_views(link.repository, link.pr_number)
    except ForgeError as error:
        return ViewedResult(error=str(error))
    if (mismatch := head_mismatch(views.head_sha, revision.head_sha)) is not None:
        return ViewedResult(error=mismatch)
    marking = _set_viewed(adapter, views.remote_id, [path for path in paths if views.viewed.get(path) is False], True)
    if not marking.done:
        return ViewedResult([], marking.failed, marking.error)
    return _confirm_head(adapter, link, revision, views.remote_id, marking)


def _confirm_head(adapter: ForgeAdapter, link: ForgeLink, revision: Revision, pull_id: str, marking: _Changed) -> ViewedResult:
    try:
        moved = head_mismatch(adapter.pull_request(link.repository, link.pr_number).head_sha, revision.head_sha)
    except ForgeError as error:
        return ViewedResult(marking.done, marking.failed, f"Could not check that the pull request did not change meanwhile: {error}")
    if moved is None:
        return ViewedResult(marking.done, marking.failed, marking.error)
    undo = _set_viewed(adapter, pull_id, marking.done, False)
    kept = [path for path in marking.done if path not in undo.done]
    note = f"{moved} It changed while files were being marked, so they were unmarked. Sync again."
    return ViewedResult(kept, marking.failed, f"{note} Could not unmark {', '.join(kept)}." if kept else note)


def _set_viewed(adapter: ForgeAdapter, pull_id: str, paths: list[str], viewed: bool) -> _Changed:
    failed: dict[str, str] = {}
    for start in range(0, len(paths), BATCH_SIZE):
        try:
            failed.update(adapter.set_files_viewed(pull_id, paths[start : start + BATCH_SIZE], viewed))
        except ForgeError as error:
            return _Changed([path for path in paths[:start] if path not in failed], failed, str(error))
    return _Changed([path for path in paths if path not in failed], failed)
