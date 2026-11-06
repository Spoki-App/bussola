from dataclasses import dataclass, replace

from bussola.errors import ConflictError, InvalidRequestError
from bussola.forge.base import BranchDeletion, ForgeAdapter, ForgeError, MergeOptions, MergeRequest
from bussola.forge.heads import HeadMismatchError, head_mismatch
from bussola.forge.pulls import MERGED_STATE, sync_conversation
from bussola.review.context import ReviewContext
from bussola.storage.models import ForgeLink


@dataclass(frozen=True)
class MergeOutcome:
    state: str
    branch_deleted: bool
    branch_error: str | None


SYNC_FIRST = "Sync to review the new commits before merging."


def review_merge_options(context: ReviewContext, adapter: ForgeAdapter, link: ForgeLink) -> MergeOptions:
    options = adapter.merge_options(link.repository, link.pr_number)
    mismatch = head_mismatch(options.head_sha, _reviewed_head(context))
    return replace(options, blockers=(*options.blockers, f"{mismatch} {SYNC_FIRST}")) if mismatch else options


def merge_pull_request(context: ReviewContext, adapter: ForgeAdapter, link: ForgeLink, request: MergeRequest, delete_branch: bool) -> MergeOutcome:
    if (mismatch := head_mismatch(request.head_sha, _reviewed_head(context))) is not None:
        raise HeadMismatchError(f"{mismatch} {SYNC_FIRST}")
    options = adapter.merge_options(link.repository, link.pr_number)
    if request.method not in options.methods:
        raise InvalidRequestError(f"This repository does not allow the {request.method.value} merge method")
    adapter.merge_pull_request(link.repository, link.pr_number, request)
    deleted, error = False, None
    if delete_branch and options.branch_deletion == BranchDeletion.OPTIONAL and options.head_branch is not None:
        try:
            adapter.delete_branch(options.head_branch)
            deleted = True
        except ForgeError as failure:
            error = f"The pull request was merged, but its branch could not be deleted: {failure}"
    try:
        state = sync_conversation(context, adapter, link).state
    except ForgeError:
        state = link.state = MERGED_STATE
    return MergeOutcome(state, deleted or options.branch_deletion == BranchDeletion.AUTOMATIC, error)


def _reviewed_head(context: ReviewContext) -> str:
    revision = context.store.reviews.latest_revision(context.review.id)
    if revision is None:
        raise ConflictError("This review has no revision yet")
    return revision.head_sha
