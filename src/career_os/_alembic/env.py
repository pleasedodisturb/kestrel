"""Alembic environment configuration."""

import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Ensure the package root is on sys.path so career_os is importable.
# This file now lives at src/career_os/_alembic/env.py (G-1350), so parents[2]
# is <repo>/src in a checkout — the directory that must be importable. In an
# installed wheel parents[2] is site-packages, which is already on sys.path, so
# the insert is a harmless no-op there.
# (Was parents[1] / "src" when this lived at <repo>/alembic/env.py; after the
# move that expression resolved to src/career_os/src, which does not exist.)
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from career_os.database import Base  # noqa: E402
from career_os.models import discovery as _discovery  # noqa: E402, F401
from career_os.models import models as _models  # noqa: E402, F401
from career_os.models import onboarding as _onboarding  # noqa: E402, F401
from career_os.models import skills as _skills  # noqa: E402, F401

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Model metadata for autogenerate support
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
