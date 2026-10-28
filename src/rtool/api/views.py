from pathlib import Path

from rtool.api.schemas import ApprovalOut, RepoOut, ReviewDetailOut, ReviewOut, ReviewPullOut, RevisionOut, RowApprovalOut, UnitOut
from rtool.review.context import ReviewContext
from rtool.review.diffs import DiffMode
from rtool.review.overview import UnitView, count_states, unit_views
from rtool.review.rows import ROW_APPROVABLE_KINDS
from rtool.review.scope import ChangeType
from rtool.review.states import DONE_STATES, UnitState
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
    latest = context.store.reviews.latest_revision(context.review.id)
    views = unit_views(context, latest) if latest else []
    counts = count_states(views)
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
        open_threads=sum(open_thread_counts(context.store, context.review.id).values()),
        total_threads=len(context.store.threads.threads(context.review.id)),
        last_session_at=last_session.completed_at if last_session else None,
        pull_request=_pull_out(context),
    )


def _pull_out(context: ReviewContext) -> ReviewPullOut | None:
    link = context.store.forge.link(context.review.id)
    if link is None:
        return None
    return ReviewPullOut(number=link.pr_number, title=link.title, url=link.url, author=link.author, state=link.state, description=link.description)


def review_detail_out(context: ReviewContext, repo: Repo) -> ReviewDetailOut:
    summary = review_out(context, repo)
    revisions = [revision_out(revision) for revision in context.store.reviews.list_revisions(context.review.id)]
    return ReviewDetailOut(**summary.model_dump(), revisions=revisions)


def unit_out(view: UnitView, open_threads: int) -> UnitOut:
    snapshot, status = view.snapshot, view.status
    kind = UnitKind(snapshot.kind)
    binary = kind == UnitKind.FILE and snapshot.base_text is None and snapshot.head_text is None
    has_approved_text = status.approval is not None and status.approval.approved_text is not None
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
        open_threads=open_threads,
        default_diff_mode=DiffMode.APPROVED if status.state == UnitState.CHANGED and has_approved_text else DiffMode.BASE,
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
