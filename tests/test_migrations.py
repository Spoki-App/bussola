from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import text

from bussola.storage.database import Database, alembic_config
from bussola.storage.models import Base


def test_migrations_produce_the_model_schema(tmp_path: Path) -> None:
    database = Database.open(tmp_path)

    with database.engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)

    assert differences == []


def test_upgrading_keeps_reviewers_that_other_rows_point_at(tmp_path: Path) -> None:
    database = Database(f"sqlite:///{tmp_path / 'bussola.db'}")
    config = alembic_config(database.url)
    with database.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "0011")
        connection.execute(text("INSERT INTO repos (path, root_commit, created_at) VALUES ('/repo', 'abc', '2026-01-01')"))
        connection.execute(text("INSERT INTO reviewers (email, name) VALUES ('a@b.c', 'Alice')"))
        connection.execute(text("INSERT INTO reviews (repo_id, head_ref, base_ref, created_at) VALUES (1, 'feature', 'main', '2026-01-01')"))
        connection.execute(
            text("INSERT INTO revisions (review_id, number, head_sha, base_sha, merge_base_sha, created_at) VALUES (1, 1, 'h', 'b', 'm', '2026-01-01')")
        )
        connection.execute(text("INSERT INTO review_sessions (review_id, reviewer_id, revision_id, id, completed_at) VALUES (1, 1, 1, 's', '2026-01-01')"))

    database.migrate()

    with database.engine.connect() as connection:
        assert connection.execute(text("SELECT name, ai FROM reviewers")).all() == [("Alice", 0)]
