"""Alembic migration environment.

Loads the ProCuGents SQLAlchemy metadata from ``src.services.db_models``
and configures the connection URL from the runtime database settings.

Run modes:

* ``alembic upgrade head`` against a configured PostgreSQL instance.
* ``alembic --sql`` for offline SQL emission.
"""

from __future__ import annotations

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make the project importable when running ``alembic`` from the repo root.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Imported AFTER sys.path fix-up so the project root resolves.
from src.services.database import DATABASE_URL  # noqa: E402
from src.services.db_models import Base  # noqa: E402

config = context.config

# URL resolution order:
#   1. ``--sql`` mode: skip; we never connect.
#   2. A pre-set option (probably via ``alembic --sql`` or programmatic
#      tests) — respect it.
#   3. Fall back to the runtime ``DATABASE_URL`` resolved by the
#      application so the CLI just works against the same DB the app uses.
configured_url = config.get_main_option("sqlalchemy.url")
if configured_url:
    DATABASE_URL_OVERRIDE = configured_url
else:
    DATABASE_URL_OVERRIDE = DATABASE_URL
config.set_main_option("sqlalchemy.url", DATABASE_URL_OVERRIDE)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Emit migration SQL to stdout without connecting to a database."""
    context.configure(
        url=DATABASE_URL_OVERRIDE,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations to the configured database."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
