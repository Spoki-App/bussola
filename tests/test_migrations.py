from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from rtool.storage.database import Database
from rtool.storage.models import Base


def test_migrations_produce_the_model_schema(tmp_path: Path) -> None:
    database = Database.open(tmp_path)

    with database.engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)

    assert differences == []
