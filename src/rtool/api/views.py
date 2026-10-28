from dataclasses import asdict
from pathlib import Path

from rtool.api.schemas import (
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
from rtool.forge.base import ForgeStatus, PullRequest
from rtool.forge.publish import PublishResult, pending_comment_count
from rtool.forge.pulls import is_pull_request_review
from rtool.review.context import ReviewContext
from rtool.review.images import image_type
from rtool.review.overview import UnitView, count_states, unit_views
from rtool.review.rows import ROW_APPROVABLE_KINDS, is_binary
from rtool.review.scope import ChangeType
from rtool.review.states import DONE_STATES
from rtool.review.threads_count import open_thread_counts
from rtool.storage.models import Approval, Repo, Revision, RowApproval
from rtool.units.model import UnitKind


def repo_out(repo: Repo) -> RepoOut:
    return RepoOut(id=repo.id, path=repo.path, name=Path(repo.path).name, root_commit=repo.root_commit, missing=not Path(repo.path).is_dir())


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
    return _review_out(context, repo, context.store.reviews.latest_revision(context.review.id))


def _review_out(context: ReviewContext, repo: Repo, latest: Revision | None) -> ReviewOut:
    views = unit_views(context, latest, texts=False) if latest else []
    counts = count_states(views)
    threads = context.store.threads.threads(context.review.id)
    last_session = context.store.reviews.last_session(context.review.id, context.reviewer.id)
    return ReviewOut(
        id=context.review.id,
        repo_id=repo.id,
        repo_path=repo.path,
        head_ref=context.review.head_ref,
        base_ref=context.review.base_ref,
        latest_revision=revision_out(latest) if latest else None,
        counts=counts,
        total=len(views),
        approved=sum(counts[state] for state in DONE_STATES),
        open_threads=sum(open_thread_counts(threads).values()),
        total_threads=len(threads),
        last_session_at=last_session.completed_at if last_session else None,
        pull_request=_pull_out(context),
        pull_request_review=is_pull_request_review(context.review),
    )


def _pull_out(context: ReviewContext) -> ReviewPullOut | None:
    link = context.store.forge.link(context.review.id)
    if link is None:
        return None
    return ReviewPullOut(number=link.pr_number, title=link.title, url=link.url, author=link.author, state=link.state, description=link.description)


def review_detail_out(context: ReviewContext, repo: Repo) -> ReviewDetailOut:
    latest = context.store.reviews.latest_revision(context.review.id)
    summary = _review_out(context, repo, latest)
    revisions = [revision_out(revision) for revision in context.store.reviews.list_revisions(context.review.id)]
    unsent = pending_comment_count(context, latest) if latest else 0
    return ReviewDetailOut(**summary.model_dump(), revisions=revisions, unsent_comments=unsent)


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
        base_start=snapshot.base_start,
        base_end=snapshot.base_end,
        head_start=snapshot.head_start,
        head_end=snapshot.head_end,
        binary=binary,
        image=image_type(snapshot.path) is not None,
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
