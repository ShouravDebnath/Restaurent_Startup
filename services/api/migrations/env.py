from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from restaurant_api import (
    edge_models,  # noqa: F401 -- include Phase 6 metadata
    workflow_models,  # noqa: F401 -- include Phase 7 metadata
)
from restaurant_api.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    supplied_connection = config.attributes.get("connection")
    if supplied_connection is not None:
        migrate(supplied_connection)
    else:
        with connectable.connect() as connection:
            migrate(connection)


def migrate(connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata, include_schemas=True)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
