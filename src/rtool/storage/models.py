import uuid
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import JSON, DateTime, Dialect, ForeignKey, Index, Text, TypeDecorator, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column

type LineNumbers = list[int | None]


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return uuid.uuid4().hex


class UtcDateTime(TypeDecorator[datetime]):
    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return value.astimezone(UTC).replace(tzinfo=None) if value else None

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        return value.replace(tzinfo=UTC) if isinstance(value, datetime) else None


class Base(MappedAsDataclass, DeclarativeBase):
    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: UtcDateTime(), LineNumbers: JSON(), str: Text()}


class Repo(Base):
    __tablename__ = "repos"

    path: Mapped[str] = mapped_column(unique=True)
    root_commit: Mapped[str] = mapped_column(index=True)
    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    created_at: Mapped[datetime] = mapped_column(default_factory=utcnow)


class Reviewer(Base):
    __tablename__ = "reviewers"

    email: Mapped[str] = mapped_column(unique=True)
    name: Mapped[str] = mapped_column()
    id: Mapped[int] = mapped_column(primary_key=True, init=False)


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("repo_id", "head_ref", "base_ref"),)

    repo_id: Mapped[int] = mapped_column(ForeignKey("repos.id"), index=True)
    head_ref: Mapped[str] = mapped_column()
    base_ref: Mapped[str] = mapped_column()
    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    created_at: Mapped[datetime] = mapped_column(default_factory=utcnow)


class Revision(Base):
    __tablename__ = "revisions"
    __table_args__ = (UniqueConstraint("review_id", "number"),)

    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id"), index=True)
    number: Mapped[int] = mapped_column()
    head_sha: Mapped[str] = mapped_column()
    base_sha: Mapped[str] = mapped_column()
    merge_base_sha: Mapped[str] = mapped_column()
    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    created_at: Mapped[datetime] = mapped_column(default_factory=utcnow)
    units_signature: Mapped[str | None] = mapped_column(default=None)


class UnitSnapshot(Base):
    __tablename__ = "unit_snapshots"

    revision_id: Mapped[int] = mapped_column(ForeignKey("revisions.id"), index=True)
    path: Mapped[str] = mapped_column()
    old_path: Mapped[str | None] = mapped_column()
    kind: Mapped[str] = mapped_column()
    qualified_name: Mapped[str] = mapped_column()
    base_hash: Mapped[str | None] = mapped_column()
    head_hash: Mapped[str | None] = mapped_column()
    base_text: Mapped[str | None] = mapped_column()
    head_text: Mapped[str | None] = mapped_column()
    base_lines: Mapped[LineNumbers] = mapped_column()
    head_lines: Mapped[LineNumbers] = mapped_column()
    base_start: Mapped[int | None] = mapped_column(default=None)
    base_end: Mapped[int | None] = mapped_column(default=None)
    head_start: Mapped[int | None] = mapped_column(default=None)
    head_end: Mapped[int | None] = mapped_column(default=None)
    id: Mapped[int] = mapped_column(primary_key=True, init=False)


class ParsedBlob(Base):
    __tablename__ = "parsed_blobs"

    object_id: Mapped[str] = mapped_column(primary_key=True)
    extractor: Mapped[str] = mapped_column(primary_key=True)
    extractor_version: Mapped[int] = mapped_column(primary_key=True)
    units: Mapped[list[dict[str, Any]]] = mapped_column(JSON)


class Approval(Base):
    __tablename__ = "approvals"
    __table_args__ = (Index("ix_approvals_review_reviewer", "review_id", "reviewer_id"),)

    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id"))
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("reviewers.id"))
    path: Mapped[str] = mapped_column()
    kind: Mapped[str] = mapped_column()
    qualified_name: Mapped[str] = mapped_column()
    head_hash: Mapped[str | None] = mapped_column()
    base_hash: Mapped[str | None] = mapped_column()
    approved_text: Mapped[str | None] = mapped_column()
    revision_id: Mapped[int] = mapped_column(ForeignKey("revisions.id"))
    id: Mapped[str] = mapped_column(primary_key=True, default_factory=new_id)
    created_at: Mapped[datetime] = mapped_column(default_factory=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)


class RowApproval(Base):
    __tablename__ = "row_approvals"
    __table_args__ = (Index("ix_row_approvals_review_reviewer", "review_id", "reviewer_id"),)

    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id"))
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("reviewers.id"))
    path: Mapped[str] = mapped_column()
    kind: Mapped[str] = mapped_column()
    qualified_name: Mapped[str] = mapped_column()
    side: Mapped[str] = mapped_column()
    row_hash: Mapped[str] = mapped_column()
    line_text: Mapped[str] = mapped_column()
    selection_id: Mapped[str] = mapped_column(index=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey("revisions.id"))
    id: Mapped[str] = mapped_column(primary_key=True, default_factory=new_id)
    created_at: Mapped[datetime] = mapped_column(default_factory=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)


class ReviewSession(Base):
    __tablename__ = "review_sessions"

    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id"), index=True)
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("reviewers.id"))
    revision_id: Mapped[int] = mapped_column(ForeignKey("revisions.id"))
    id: Mapped[str] = mapped_column(primary_key=True, default_factory=new_id)
    completed_at: Mapped[datetime] = mapped_column(default_factory=utcnow)


class Thread(Base):
    __tablename__ = "threads"

    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id"), index=True)
    scope: Mapped[str] = mapped_column()
    created_by: Mapped[int] = mapped_column(ForeignKey("reviewers.id"))
    created_revision_id: Mapped[int] = mapped_column(ForeignKey("revisions.id"))
    path: Mapped[str | None] = mapped_column(default=None)
    kind: Mapped[str | None] = mapped_column(default=None)
    qualified_name: Mapped[str | None] = mapped_column(default=None)
    side: Mapped[str | None] = mapped_column(default=None)
    unit_hash: Mapped[str | None] = mapped_column(default=None)
    line_offset: Mapped[int | None] = mapped_column(default=None)
    line_text: Mapped[str | None] = mapped_column(default=None)
    context_before: Mapped[list[str]] = mapped_column(JSON, default_factory=list)
    context_after: Mapped[list[str]] = mapped_column(JSON, default_factory=list)
    status: Mapped[str] = mapped_column(default="open")
    id: Mapped[str] = mapped_column(primary_key=True, default_factory=new_id)
    created_at: Mapped[datetime] = mapped_column(default_factory=utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)


class Comment(Base):
    __tablename__ = "comments"

    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.id"), index=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("reviewers.id"))
    body: Mapped[str] = mapped_column()
    id: Mapped[str] = mapped_column(primary_key=True, default_factory=new_id)
    created_at: Mapped[datetime] = mapped_column(default_factory=utcnow)
    edited_at: Mapped[datetime | None] = mapped_column(default=None)
    deleted_at: Mapped[datetime | None] = mapped_column(default=None)


class ThreadAnchor(Base):
    __tablename__ = "thread_anchors"
    __table_args__ = (UniqueConstraint("thread_id", "revision_id"),)

    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.id"), index=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey("revisions.id"))
    path: Mapped[str | None] = mapped_column()
    kind: Mapped[str | None] = mapped_column()
    qualified_name: Mapped[str | None] = mapped_column()
    unit_hash: Mapped[str | None] = mapped_column()
    line_offset: Mapped[int | None] = mapped_column()
    outdated: Mapped[bool] = mapped_column(default=False)
    id: Mapped[int] = mapped_column(primary_key=True, init=False)


class ForgeLink(Base):
    __tablename__ = "forge_links"

    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id"), unique=True)
    provider: Mapped[str] = mapped_column()
    repository: Mapped[str] = mapped_column()
    pr_number: Mapped[int] = mapped_column()
    title: Mapped[str | None] = mapped_column(default=None)
    author: Mapped[str | None] = mapped_column(default=None)
    url: Mapped[str | None] = mapped_column(default=None)
    state: Mapped[str | None] = mapped_column(default=None)
    description: Mapped[str | None] = mapped_column(default=None)
    synced_at: Mapped[datetime | None] = mapped_column(default=None)
    id: Mapped[int] = mapped_column(primary_key=True, init=False)
    created_at: Mapped[datetime] = mapped_column(default_factory=utcnow)


class PublishedComment(Base):
    __tablename__ = "published_comments"

    comment_id: Mapped[str] = mapped_column(ForeignKey("comments.id"), primary_key=True)
    provider: Mapped[str] = mapped_column()
    remote_id: Mapped[str | None] = mapped_column()
    remote_url: Mapped[str | None] = mapped_column()
    published_body_hash: Mapped[str] = mapped_column()
    published_at: Mapped[datetime] = mapped_column(default_factory=utcnow)
    remote_body_hash: Mapped[str | None] = mapped_column(default=None)
