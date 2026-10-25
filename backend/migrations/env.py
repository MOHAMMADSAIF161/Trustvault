
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import DATABASE_URL
from app.database import Base
from app import models  # Register all models

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_database_url():
    if not DATABASE_URL:
        raise RuntimeError("Application database URL is missing.")
    return DATABASE_URL


def run_migrations_offline() -> None:
    url = get_database_url()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        get_database_url(),
        poolclass=pool.NullPool,
    )

    try:
        with connectable.connect() as connection:
            if connection.dialect.name != "postgresql":
                raise RuntimeError(
                    "TrustVault migrations require PostgreSQL."
                )

            database_name = connection.exec_driver_sql(
                "SELECT current_database()"
            ).scalar_one()

            if database_name != "trustvault_test":
                raise RuntimeError(
                    "Safety check failed: migrations are allowed "
                    f"only on trustvault_test. Current database: "
                    f"{database_name}"
                )

            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
