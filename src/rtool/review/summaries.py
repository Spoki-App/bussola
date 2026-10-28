from collections import defaultdict
from dataclasses import dataclass, field

from rtool.review.states import ApprovalSet, UnitStatus, compute_statuses
from rtool.storage.models import Approval, ForgeLink, Review, Reviewer, ReviewSession, Revision, RowApproval, Thread, UnitSnapshot
from rtool.storage.repositories import Store


@dataclass(frozen=True)
class ReviewData:
    review: Review
    latest: Revision | None
    statuses: list[UnitStatus]
    threads: list[Thread] = field(default_factory=list)
    last_session: ReviewSession | None = None
    link: ForgeLink | None = None


def load_review_data(store: Store, reviews: list[Review], reviewer: Reviewer) -> list[ReviewData]:
    ids = [review.id for review in reviews]
    latest = store.reviews.latest_revisions(ids)
    snapshots: defaultdict[int, list[UnitSnapshot]] = defaultdict(list)
    for snapshot in store.reviews.snapshots_of([revision.id for revision in latest.values()], texts=False):
        snapshots[snapshot.revision_id].append(snapshot)
    approvals = _by_review(store.approvals.approvals_of(ids, reviewer.id))
    rows = _by_review(store.approvals.row_approvals_of(ids, reviewer.id))
    threads = _by_review(store.threads.threads_of(ids))
    sessions = store.reviews.last_sessions(ids, reviewer.id)
    links = store.forge.links_of(ids)
    data: list[ReviewData] = []
    for review in reviews:
        revision = latest.get(review.id)
        units = snapshots[revision.id] if revision else []
        statuses = compute_statuses(units, ApprovalSet(approvals[review.id], rows[review.id]))
        data.append(ReviewData(review, revision, [statuses[unit.id] for unit in units], threads[review.id], sessions.get(review.id), links.get(review.id)))
    return data


def _by_review[T: Approval | RowApproval | Thread](items: list[T]) -> defaultdict[int, list[T]]:
    grouped: defaultdict[int, list[T]] = defaultdict(list)
    for item in items:
        grouped[item.review_id].append(item)
    return grouped
