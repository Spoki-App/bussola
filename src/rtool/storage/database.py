import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import platformdirs
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry

APP_NAME = "rtool"
DATA_DIR_ENV = "RTOOL_DATA_DIR"
DATABASE_FILE = "rtool.db"
MIGRATIONS_DIR = Path(__file__).parent / "migrations"
SQLITE_PRAGMAS = ("PRAGMA foreign_keys=ON", "PRAGMA journal_mode=WAL", "PRAGMA busy_timeout=5000")


def default_data_dir() -> Path:
    override = os.environ.get(DATA_DIR_ENV)
    return Path(override) if override else Path(platformdirs.user_data_dir(APP_NAME))


def alembic_config(url: str) -> Config:
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    config.set_main_option("sqlalchemy.url", url)
    return config


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        self.engine: Engine = create_engine(url, connect_args={"check_same_thread": False})
        event.listen(self.engine, "connect", _apply_pragmas)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    @classmethod
    def open(cls, data_dir: Path) -> "Database":
        data_dir.mkdir(parents=True, exist_ok=True)
        database = cls(f"sqlite:///{data_dir / DATABASE_FILE}")
        database.migrate()
        return database

    def migrate(self) -> None:
        config = alembic_config(self.url)
        with self.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

    @contextmanager
    def session(self) -> Generator[Session]:
        with self._sessions() as session:
            yield session


def _apply_pragmas(connection: DBAPIConnection, _record: ConnectionPoolEntry) -> None:
    cursor = connection.cursor()
    for pragma in SQLITE_PRAGMAS:
        cursor.execute(pragma)
    cursor.close()
