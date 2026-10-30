from sqlalchemy import func, select
from sqlalchemy.orm import Session, defer

from bussola.storage.models import (
    Approval,
    Comment,
    ForgeLink,
    PublishedComment,
    Repo,
    Review,
    Reviewer,
    ReviewSession,
    Revision,
    RowApproval,
    Thread,
    ThreadAnchor,
    UnitSnapshot,
)

SNAPSHOT_TEXT_COLUMNS = (UnitSnapshot.base_text, UnitSnapshot.head_text, UnitSnapshot.base_lines, UnitSnapshot.head_lines)


class _SqlRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _add[T](self, entity: T) -> T:
        self._session.add(entity)
        self._session.flush()
        return entity


class SqlReviewRepository(_SqlRepository):
    def list_repos(self) -> list[Repo]:
        return list(self._session.scalars(select(Repo).order_by(Repo.id)))

    def get_repo(self, repo_id: int) -> Repo | None:
        return self._session.get(Repo, repo_id)

    def find_repo_by_path(self, path: str) -> Repo | None:
        return self._session.scalar(select(Repo).where(Repo.path == path))

    def find_repo_by_root(self, root_commit: str) -> Repo | None:
        return self._session.scalar(select(Repo).where(Repo.root_commit == root_commit).order_by(Repo.id))

    def add_repo(self, repo: Repo) -> Repo:
        return self._add(repo)

    def list_reviews(self, repo_id: int) -> list[Review]:
        return list(self._session.scalars(select(Review).where(Review.repo_id == repo_id).order_by(Review.id.desc())))

    def get_review(self, review_id: int) -> Review | None:
        return self._session.get(Review, review_id)

    def find_review(self, repo_id: int, head_ref: str, base_ref: str) -> Review | None:
        query = select(Review).where(Review.repo_id == repo_id, Review.head_ref == head_ref, Review.base_ref == base_ref)
        return self._session.scalar(query)

    def find_or_add_review(self, repo_id: int, head_ref: str, base_ref: str) -> Review:
        return self.find_review(repo_id, head_ref, base_ref) or self.add_review(Review(repo_id=repo_id, head_ref=head_ref, base_ref=base_ref))

    def add_review(self, review: Review) -> Review:
        return self._add(review)

    def latest_revision(self, review_id: int) -> Revision | None:
        return self._session.scalar(select(Revision).where(Revision.review_id == review_id).order_by(Revision.number.desc()).limit(1))

    def latest_revisions(self, review_ids: list[int]) -> dict[int, Revision]:
        latest = (
            select(Revision.review_id, func.max(Revision.number).label("number"))
            .where(Revision.review_id.in_(review_ids))
            .group_by(Revision.review_id)
            .subquery()
        )
        query = select(Revision).join(latest, (Revision.review_id == latest.c.review_id) & (Revision.number == latest.c.number))
        return {revision.review_id: revision for revision in self._session.scalars(query)}

    def get_revision(self, revision_id: int) -> Revision | None:
        return self._session.get(Revision, revision_id)

    def add_revision(self, revision: Revision, snapshots: list[UnitSnapshot]) -> Revision:
        self._add(revision)
        for snapshot in snapshots:
            snapshot.revision_id = revision.id
        self._session.add_all(snapshots)
        self._session.flush()
        return revision

    def snapshots(self, revision_id: int, *, texts: bool = True) -> list[UnitSnapshot]:
        return self.snapshots_of([revision_id], texts=texts)

    def snapshots_of(self, revision_ids: list[int], *, texts: bool = True) -> list[UnitSnapshot]:
        query = select(UnitSnapshot).where(UnitSnapshot.revision_id.in_(revision_ids)).order_by(UnitSnapshot.path, UnitSnapshot.id)
        if not texts:
            query = query.options(*(defer(column) for column in SNAPSHOT_TEXT_COLUMNS))
        return list(self._session.scalars(query))

    def get_snapshot(self, snapshot_id: int) -> UnitSnapshot | None:
        return self._session.get(UnitSnapshot, snapshot_id)

    def reviewer(self, email: str, name: str) -> Reviewer:
        existing = self._session.scalar(select(Reviewer).where(Reviewer.email == email))
        if existing is None:
            return self._add(Reviewer(email=email, name=name))
        if existing.name != name:
            existing.name = name
        return existing

    def get_reviewer(self, reviewer_id: int) -> Reviewer | None:
        return self._session.get(Reviewer, reviewer_id)

    def add_session(self, review_session: ReviewSession) -> ReviewSession:
        return self._add(review_session)

    def last_session(self, review_id: int, reviewer_id: int) -> ReviewSession | None:
        return self.last_sessions([review_id], reviewer_id).get(review_id)

    def last_sessions(self, review_ids: list[int], reviewer_id: int) -> dict[int, ReviewSession]:
        query = (
            select(ReviewSession).where(ReviewSession.review_id.in_(review_ids), ReviewSession.reviewer_id == reviewer_id).order_by(ReviewSession.completed_at)
        )
        return {review_session.review_id: review_session for review_session in self._session.scalars(query)}


class SqlApprovalRepository(_SqlRepository):
    def approvals(self, review_id: int, reviewer_id: int) -> list[Approval]:
        return self.approvals_of([review_id], reviewer_id)

    def approvals_of(self, review_ids: list[int], reviewer_id: int) -> list[Approval]:
        query = select(Approval).where(Approval.review_id.in_(review_ids), Approval.reviewer_id == reviewer_id).order_by(Approval.created_at)
        return list(self._session.scalars(query.options(defer(Approval.approved_text))))

    def get_approval(self, approval_id: str) -> Approval | None:
        return self._session.get(Approval, approval_id)

    def add_approvals(self, approvals: list[Approval]) -> list[Approval]:
        self._session.add_all(approvals)
        self._session.flush()
        return approvals

    def row_approvals(self, review_id: int, reviewer_id: int) -> list[RowApproval]:
        return self.row_approvals_of([review_id], reviewer_id)

    def row_approvals_of(self, review_ids: list[int], reviewer_id: int) -> list[RowApproval]:
        query = select(RowApproval).where(RowApproval.review_id.in_(review_ids), RowApproval.reviewer_id == reviewer_id).order_by(RowApproval.created_at)
        return list(self._session.scalars(query))

    def add_row_approvals(self, rows: list[RowApproval]) -> list[RowApproval]:
        self._session.add_all(rows)
        self._session.flush()
        return rows

    def selection(self, selection_id: str) -> list[RowApproval]:
        return list(self._session.scalars(select(RowApproval).where(RowApproval.selection_id == selection_id)))


class SqlThreadRepository(_SqlRepository):
    def threads(self, review_id: int) -> list[Thread]:
        return self.threads_of([review_id])

    def threads_of(self, review_ids: list[int]) -> list[Thread]:
        query = select(Thread).where(Thread.review_id.in_(review_ids), Thread.deleted_at.is_(None)).order_by(Thread.created_at)
        return list(self._session.scalars(query))

    def get_thread(self, thread_id: str) -> Thread | None:
        thread = self._session.get(Thread, thread_id)
        return thread if thread is not None and thread.deleted_at is None else None

    def add_thread(self, thread: Thread) -> Thread:
        return self._add(thread)

    def comments(self, thread_ids: list[str]) -> list[Comment]:
        return list(self._session.scalars(select(Comment).where(Comment.thread_id.in_(thread_ids)).order_by(Comment.created_at)))

    def get_comment(self, comment_id: str) -> Comment | None:
        return self._session.get(Comment, comment_id)

    def add_comment(self, comment: Comment) -> Comment:
        return self._add(comment)

    def anchors(self, thread_ids: list[str]) -> list[ThreadAnchor]:
        query = select(ThreadAnchor).where(ThreadAnchor.thread_id.in_(thread_ids)).order_by(ThreadAnchor.revision_id)
        return list(self._session.scalars(query))

    def add_anchor(self, anchor: ThreadAnchor) -> ThreadAnchor:
        return self._add(anchor)


class SqlForgeRepository(_SqlRepository):
    def link(self, review_id: int) -> ForgeLink | None:
        return self.links_of([review_id]).get(review_id)

    def links_of(self, review_ids: list[int]) -> dict[int, ForgeLink]:
        return {link.review_id: link for link in self._session.scalars(select(ForgeLink).where(ForgeLink.review_id.in_(review_ids)))}

    def links_for_repo(self, repo_id: int) -> list[ForgeLink]:
        query = select(ForgeLink).join(Review, Review.id == ForgeLink.review_id).where(Review.repo_id == repo_id).order_by(ForgeLink.pr_number)
        return list(self._session.scalars(query))

    def save_link(self, link: ForgeLink) -> ForgeLink:
        existing = self.link(link.review_id)
        if existing is None:
            self._session.add(link)
            self._session.flush()
            return link
        existing.provider, existing.repository, existing.pr_number = link.provider, link.repository, link.pr_number
        if link.synced_at is not None:
            existing.title, existing.author, existing.url, existing.state = link.title, link.author, link.url, link.state
            existing.description = link.description
            existing.synced_at = link.synced_at
        return existing

    def published(self, comment_ids: list[str]) -> dict[str, PublishedComment]:
        rows = self._session.scalars(select(PublishedComment).where(PublishedComment.comment_id.in_(comment_ids)))
        return {row.comment_id: row for row in rows}

    def published_by_remote(self, provider: str, remote_ids: list[str]) -> list[PublishedComment]:
        query = select(PublishedComment).where(PublishedComment.provider == provider, PublishedComment.remote_id.in_(remote_ids))
        return list(self._session.scalars(query))

    def save_published(self, published: PublishedComment) -> PublishedComment:
        merged = self._session.merge(published)
        self._session.flush()
        return merged


class Store:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.reviews = SqlReviewRepository(session)
        self.approvals = SqlApprovalRepository(session)
        self.threads = SqlThreadRepository(session)
        self.forge = SqlForgeRepository(session)

    def commit(self) -> None:
        self.session.commit()
