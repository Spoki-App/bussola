import json
from dataclasses import dataclass

from rtool.config import load_repo_config
from rtool.git import GitRepo
from rtool.review.anchoring import reanchor_threads
from rtool.review.refs import resolve_review_commits
from rtool.review.scope import UnitChange, compute_scope
from rtool.storage.models import Review, Revision, UnitSnapshot
from rtool.storage.repositories import Store
from rtool.storage.unit_cache import SqlUnitCache
from rtool.units.extract import FileUnitExtractor


@dataclass(frozen=True)
class RefreshResult:
    revision: Revision
    created: bool


def refresh_review(store: Store, review: Review, repo: GitRepo, *, fetch: bool = False) -> RefreshResult:
    if fetch:
        fetch_review_remotes(repo, review)
    commits = resolve_review_commits(repo, review.head_ref, review.base_ref)
    previous = store.reviews.latest_revision(review.id)
    extractor = FileUnitExtractor(load_repo_config(repo.root), SqlUnitCache(store.session))
    signature = extractor.signature()
    commit_shas = (commits.head_sha, commits.base_sha, commits.merge_base_sha)
    same_commits = previous is not None and (previous.head_sha, previous.base_sha, previous.merge_base_sha) == commit_shas
    if previous is not None and same_commits and previous.units_signature == signature:
        return _refreshed(store, review, previous, created=False)
    snapshots = [snapshot_from(change) for change in compute_scope(repo, commits.merge_base_sha, commits.head_sha, extractor)]
    if previous is not None and same_commits and _same_units(store.reviews.snapshots(previous.id, texts=False), snapshots):
        previous.units_signature = signature
        return _refreshed(store, review, previous, created=False)
    revision = Revision(
        review_id=review.id,
        number=previous.number + 1 if previous else 1,
        head_sha=commits.head_sha,
        base_sha=commits.base_sha,
        merge_base_sha=commits.merge_base_sha,
        units_signature=signature,
    )
    store.reviews.add_revision(revision, snapshots)
    return _refreshed(store, review, revision, created=True)


def _refreshed(store: Store, review: Review, revision: Revision, *, created: bool) -> RefreshResult:
    reanchor_threads(store, review, revision)
    return RefreshResult(revision, created)


def fetch_review_remotes(repo: GitRepo, review: Review) -> None:
    remotes = {remote for ref in (review.head_ref, review.base_ref) if (remote := repo.upstream_remote(ref)) is not None}
    for remote in sorted(remotes):
        repo.fetch(remote)


def _same_units(stored: list[UnitSnapshot], computed: list[UnitSnapshot]) -> bool:
    return sorted(map(_unit_identity, stored)) == sorted(map(_unit_identity, computed))


def _unit_identity(snapshot: UnitSnapshot) -> tuple[str, str, str, str, str, str, str]:
    return (
        snapshot.path,
        snapshot.old_path or "",
        snapshot.kind,
        snapshot.qualified_name,
        snapshot.base_hash or "",
        snapshot.head_hash or "",
        json.dumps([snapshot.base_lines, snapshot.head_lines]),
    )


def snapshot_from(change: UnitChange) -> UnitSnapshot:
    base, head = change.base, change.head
    return UnitSnapshot(
        revision_id=0,
        path=change.key.path,
        old_path=change.old_path,
        kind=change.key.kind.value,
        qualified_name=change.key.qualified_name,
        base_hash=change.base_hash,
        head_hash=change.head_hash,
        base_text=base.text if base else None,
        head_text=head.text if head else None,
        base_lines=list(base.line_numbers) if base else [],
        head_lines=list(head.line_numbers) if head else [],
        base_start=base.start_line if base else None,
        base_end=base.end_line if base else None,
        head_start=head.start_line if head else None,
        head_end=head.end_line if head else None,
    )
