from alembic import context
from sqlalchemy import Connection, engine_from_config, pool

from bussola.storage.models import Base

config = context.config


def run_with_connection(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations() -> None:
    existing = config.attributes.get("connection")
    if isinstance(existing, Connection):
        run_with_connection(existing)
        return
    engine = engine_from_config(config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool)
    with engine.connect() as connection:
        run_with_connection(connection)


run_migrations()
