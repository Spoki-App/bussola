from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session

from rtool.storage.models import (
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


class ReviewRepository(Protocol):
    def list_repos(self) -> list[Repo]: ...
    def get_repo(self, repo_id: int) -> Repo | None: ...
    def find_repo_by_path(self, path: str) -> Repo | None: ...
    def find_repo_by_root(self, root_commit: str) -> Repo | None: ...
    def add_repo(self, repo: Repo) -> Repo: ...
    def list_reviews(self, repo_id: int) -> list[Review]: ...
    def get_review(self, review_id: int) -> Review | None: ...
    def find_review(self, repo_id: int, head_ref: str, base_ref: str) -> Review | None: ...
    def add_review(self, review: Review) -> Review: ...
    def latest_revision(self, review_id: int) -> Revision | None: ...
    def list_revisions(self, review_id: int) -> list[Revision]: ...
    def get_revision(self, revision_id: int) -> Revision | None: ...
    def add_revision(self, revision: Revision, snapshots: list[UnitSnapshot]) -> Revision: ...
    def snapshots(self, revision_id: int) -> list[UnitSnapshot]: ...
    def get_snapshot(self, snapshot_id: int) -> UnitSnapshot | None: ...
    def reviewer(self, email: str, name: str) -> Reviewer: ...
    def get_reviewer(self, reviewer_id: int) -> Reviewer | None: ...
    def add_session(self, review_session: ReviewSession) -> ReviewSession: ...
    def last_session(self, review_id: int, reviewer_id: int) -> ReviewSession | None: ...


class ApprovalRepository(Protocol):
    def approvals(self, review_id: int, reviewer_id: int) -> list[Approval]: ...
    def get_approval(self, approval_id: str) -> Approval | None: ...
    def add_approvals(self, approvals: list[Approval]) -> list[Approval]: ...
    def row_approvals(self, review_id: int, reviewer_id: int) -> list[RowApproval]: ...
    def add_row_approvals(self, rows: list[RowApproval]) -> list[RowApproval]: ...
    def selection(self, selection_id: str) -> list[RowApproval]: ...


class ThreadRepository(Protocol):
    def threads(self, review_id: int) -> list[Thread]: ...
    def get_thread(self, thread_id: str) -> Thread | None: ...
    def add_thread(self, thread: Thread) -> Thread: ...
    def comments(self, thread_ids: list[str]) -> list[Comment]: ...
    def get_comment(self, comment_id: str) -> Comment | None: ...
    def add_comment(self, comment: Comment) -> Comment: ...
    def anchors(self, thread_ids: list[str]) -> list[ThreadAnchor]: ...
    def add_anchor(self, anchor: ThreadAnchor) -> ThreadAnchor: ...


class ForgeRepository(Protocol):
    def link(self, review_id: int) -> ForgeLink | None: ...
    def links_for_repo(self, repo_id: int) -> list[ForgeLink]: ...
    def save_link(self, link: ForgeLink) -> ForgeLink: ...
    def published(self, comment_ids: list[str]) -> dict[str, PublishedComment]: ...
    def published_by_remote(self, provider: str, remote_ids: list[str]) -> list[PublishedComment]: ...
    def save_published(self, published: PublishedComment) -> PublishedComment: ...


class SqlReviewRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

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

    def add_review(self, review: Review) -> Review:
        return self._add(review)

    def latest_revision(self, review_id: int) -> Revision | None:
        return self._session.scalar(select(Revision).where(Revision.review_id == review_id).order_by(Revision.number.desc()).limit(1))

    def list_revisions(self, review_id: int) -> list[Revision]:
        return list(self._session.scalars(select(Revision).where(Revision.review_id == review_id).order_by(Revision.number)))

    def get_revision(self, revision_id: int) -> Revision | None:
        return self._session.get(Revision, revision_id)

    def add_revision(self, revision: Revision, snapshots: list[UnitSnapshot]) -> Revision:
        self._add(revision)
        for snapshot in snapshots:
            snapshot.revision_id = revision.id
        self._session.add_all(snapshots)
        self._session.flush()
        return revision

    def snapshots(self, revision_id: int) -> list[UnitSnapshot]:
        query = select(UnitSnapshot).where(UnitSnapshot.revision_id == revision_id).order_by(UnitSnapshot.path, UnitSnapshot.id)
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
        query = (
            select(ReviewSession)
            .where(ReviewSession.review_id == review_id, ReviewSession.reviewer_id == reviewer_id)
            .order_by(ReviewSession.completed_at.desc())
            .limit(1)
        )
        return self._session.scalar(query)

    def _add[T](self, entity: T) -> T:
        self._session.add(entity)
        self._session.flush()
        return entity


class SqlApprovalRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def approvals(self, review_id: int, reviewer_id: int) -> list[Approval]:
        query = select(Approval).where(Approval.review_id == review_id, Approval.reviewer_id == reviewer_id).order_by(Approval.created_at)
        return list(self._session.scalars(query))

    def get_approval(self, approval_id: str) -> Approval | None:
        return self._session.get(Approval, approval_id)

    def add_approvals(self, approvals: list[Approval]) -> list[Approval]:
        self._session.add_all(approvals)
        self._session.flush()
        return approvals

    def row_approvals(self, review_id: int, reviewer_id: int) -> list[RowApproval]:
        query = select(RowApproval).where(RowApproval.review_id == review_id, RowApproval.reviewer_id == reviewer_id).order_by(RowApproval.created_at)
        return list(self._session.scalars(query))

    def add_row_approvals(self, rows: list[RowApproval]) -> list[RowApproval]:
        self._session.add_all(rows)
        self._session.flush()
        return rows

    def selection(self, selection_id: str) -> list[RowApproval]:
        return list(self._session.scalars(select(RowApproval).where(RowApproval.selection_id == selection_id)))


class SqlThreadRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def threads(self, review_id: int) -> list[Thread]:
        query = select(Thread).where(Thread.review_id == review_id, Thread.deleted_at.is_(None)).order_by(Thread.created_at)
        return list(self._session.scalars(query))

    def get_thread(self, thread_id: str) -> Thread | None:
        thread = self._session.get(Thread, thread_id)
        return thread if thread is not None and thread.deleted_at is None else None

    def add_thread(self, thread: Thread) -> Thread:
        self._session.add(thread)
        self._session.flush()
        return thread

    def comments(self, thread_ids: list[str]) -> list[Comment]:
        return list(self._session.scalars(select(Comment).where(Comment.thread_id.in_(thread_ids)).order_by(Comment.created_at)))

    def get_comment(self, comment_id: str) -> Comment | None:
        return self._session.get(Comment, comment_id)

    def add_comment(self, comment: Comment) -> Comment:
        self._session.add(comment)
        self._session.flush()
        return comment

    def anchors(self, thread_ids: list[str]) -> list[ThreadAnchor]:
        query = select(ThreadAnchor).where(ThreadAnchor.thread_id.in_(thread_ids)).order_by(ThreadAnchor.revision_id)
        return list(self._session.scalars(query))

    def add_anchor(self, anchor: ThreadAnchor) -> ThreadAnchor:
        self._session.add(anchor)
        self._session.flush()
        return anchor


class SqlForgeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def link(self, review_id: int) -> ForgeLink | None:
        return self._session.scalar(select(ForgeLink).where(ForgeLink.review_id == review_id))

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
        self.reviews: ReviewRepository = SqlReviewRepository(session)
        self.approvals: ApprovalRepository = SqlApprovalRepository(session)
        self.threads: ThreadRepository = SqlThreadRepository(session)
        self.forge: ForgeRepository = SqlForgeRepository(session)

    def commit(self) -> None:
        self.session.commit()
