from collections import Counter
from dataclasses import asdict
from pathlib import Path

from bussola.api.schemas import (
    ApprovalOut,
    ForgeStatusOut,
    PublishOut,
    PublishOutcomeOut,
    PullRequestOut,
    RepoOut,
    ReviewDetailOut,
    ReviewOut,
    ReviewPullOut,
    RevisionOut,
    RowApprovalOut,
    UnitOut,
)
from bussola.forge.base import ForgeStatus, PullRequest
from bussola.forge.publish import PublishResult, pending_comment_count
from bussola.forge.pulls import is_pull_request_review
from bussola.review.context import ReviewContext
from bussola.review.images import image_type
from bussola.review.overview import UnitView
from bussola.review.rows import ROW_APPROVABLE_KINDS, is_binary
from bussola.review.scope import ChangeType
from bussola.review.states import DONE_STATES, UnitState
from bussola.review.summaries import ReviewData, load_review_data
from bussola.review.threads_count import open_thread_counts
from bussola.storage.models import Approval, ForgeLink, Repo, Revision, RowApproval
from bussola.units.model import UnitKind


def repo_out(repo: Repo) -> RepoOut:
    return RepoOut(id=repo.id, path=repo.path, name=Path(repo.path).name, missing=not Path(repo.path).is_dir())


def revision_out(revision: Revision) -> RevisionOut:
    return RevisionOut(
        id=revision.id,
        number=revision.number,
        head_sha=revision.head_sha,
        base_sha=revision.base_sha,
        merge_base_sha=revision.merge_base_sha,
        created_at=revision.created_at,
    )


def review_out(context: ReviewContext, repo: Repo) -> ReviewOut:
    return review_summary_out(load_review_data(context.store, [context.review], context.reviewer)[0], repo)


def review_summary_out(data: ReviewData, repo: Repo) -> ReviewOut:
    states = Counter(status.state for status in data.statuses)
    counts = {state: states.get(state, 0) for state in UnitState}
    review, link = data.review, data.link
    return ReviewOut(
        id=review.id,
        repo_id=repo.id,
        repo_path=repo.path,
        head_ref=review.head_ref,
        base_ref=review.base_ref,
        latest_revision=revision_out(data.latest) if data.latest else None,
        counts=counts,
        total=len(data.statuses),
        approved=sum(counts[state] for state in DONE_STATES),
        open_threads=sum(open_thread_counts(data.threads).values()),
        total_threads=len(data.threads),
        last_session_at=data.last_session.completed_at if data.last_session else None,
        pull_request=_pull_out(link) if link else None,
        pull_request_review=is_pull_request_review(review),
    )


def _pull_out(link: ForgeLink) -> ReviewPullOut:
    return ReviewPullOut(number=link.pr_number, title=link.title, url=link.url, author=link.author, state=link.state, description=link.description)


def review_detail_out(context: ReviewContext, repo: Repo) -> ReviewDetailOut:
    data = load_review_data(context.store, [context.review], context.reviewer)[0]
    unsent = pending_comment_count(context, data.latest) if data.latest else 0
    return ReviewDetailOut(**review_summary_out(data, repo).model_dump(), unsent_comments=unsent)


def publish_out(result: PublishResult) -> PublishOut:
    outcomes = [PublishOutcomeOut(comment_ids=list(item.comment_ids), status=item.status.value, detail=item.detail, url=item.url) for item in result.outcomes]
    return PublishOut(review_url=result.review_url, outcomes=outcomes)


def unit_out(view: UnitView, open_threads: int) -> UnitOut:
    snapshot, status = view.snapshot, view.status
    kind = UnitKind(snapshot.kind)
    binary = is_binary(snapshot)
    return UnitOut(
        id=snapshot.id,
        revision_id=snapshot.revision_id,
        path=snapshot.path,
        old_path=snapshot.old_path,
        kind=snapshot.kind,
        qualified_name=snapshot.qualified_name,
        state=status.state,
        change_type=_change_type(snapshot.base_hash, snapshot.head_hash),
        base_changed=status.base_changed,
        approval_id=status.approval.id if status.approval else None,
        row_approvable=kind in ROW_APPROVABLE_KINDS and not binary,
        rows_total=status.rows_total,
        rows_approved=len(status.approved_row_hashes),
        binary=binary,
        image=image_type(snapshot.path) is not None,
        todo=status.is_todo,
        action=status.action(removed=snapshot.head_hash is None),
        open_threads=open_threads,
    )


def approval_out(approval: Approval) -> ApprovalOut:
    return ApprovalOut(
        id=approval.id,
        path=approval.path,
        kind=approval.kind,
        qualified_name=approval.qualified_name,
        head_hash=approval.head_hash,
        created_at=approval.created_at,
        revoked_at=approval.revoked_at,
    )


def row_approval_out(row: RowApproval) -> RowApprovalOut:
    return RowApprovalOut(id=row.id, selection_id=row.selection_id, side=row.side, line_text=row.line_text)


def _change_type(base_hash: str | None, head_hash: str | None) -> ChangeType:
    if base_hash is None:
        return ChangeType.ADDED
    return ChangeType.REMOVED if head_hash is None else ChangeType.MODIFIED


def pull_request_out(pull: PullRequest) -> PullRequestOut:
    return PullRequestOut(**asdict(pull))


def forge_status_out(status: ForgeStatus) -> ForgeStatusOut:
    return ForgeStatusOut(**asdict(status))
