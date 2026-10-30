from dataclasses import dataclass
from itertools import batched

from bussola.forge.base import ForgeAdapter, ForgeError
from bussola.forge.publish import head_mismatch
from bussola.review.context import ReviewContext
from bussola.review.overview import complete_paths, unit_views
from bussola.storage.models import ForgeLink, Revision

MARK_BATCH_SIZE = 50
NOT_IN_PULL_REQUEST = "Not changed in the pull request"


@dataclass(frozen=True)
class ViewedResult:
    marked: list[str]
    failed: dict[str, str]
    error: str | None = None


def mark_approved_files_viewed(context: ReviewContext, adapter: ForgeAdapter, link: ForgeLink, revision: Revision) -> ViewedResult:
    paths = complete_paths(unit_views(context, revision, texts=False))
    if not paths:
        return ViewedResult([], {})
    try:
        views = adapter.file_views(link.repository, link.pr_number)
    except ForgeError as error:
        return ViewedResult([], {}, str(error))
    if (mismatch := head_mismatch(views.head_sha, revision.head_sha)) is not None:
        return ViewedResult([], {}, mismatch)
    failed = {path: NOT_IN_PULL_REQUEST for path in paths if path not in views.viewed}
    to_mark = [path for path in paths if path in views.viewed and not views.viewed[path]]
    for batch in batched(to_mark, MARK_BATCH_SIZE):
        failed.update(_mark(adapter, views.remote_id, list(batch)))
    return ViewedResult([path for path in to_mark if path not in failed], failed)


def _mark(adapter: ForgeAdapter, pull_id: str, paths: list[str]) -> dict[str, str]:
    try:
        adapter.mark_files_viewed(pull_id, paths)
    except ForgeError as error:
        if len(paths) == 1:
            return {paths[0]: str(error)}
        return {path: reason for single in paths for path, reason in _mark(adapter, pull_id, [single]).items()}
    return {}
