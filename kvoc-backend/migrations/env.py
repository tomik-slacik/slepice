import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# lets this run as `alembic ...` from kvoc-backend/ without the project
# being pip-installed - same "just works, no packaging step" spirit as the
# rest of this project (see run.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config as app_config  # noqa: E402
from app import models  # noqa: E402  (import registers every model on Base)
from app.database import Base  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Real DB URL comes from the app's own config (env var KVOC_DATABASE_URL,
# same one main.py/database.py use) rather than a second hardcoded copy in
# alembic.ini - one source of truth for "which database", not two that can
# drift apart. alembic.ini's sqlalchemy.url is left blank on purpose.
config.set_main_option("sqlalchemy.url", app_config.DATABASE_URL)

# Interpret the config file for Python logging - but not when the app
# itself invokes Alembic programmatically at boot (see database.py's
# init_db()), since that would stomp on app/logging_setup.py's own
# structured logging config on every single startup. CLI use (`alembic
# upgrade head` from a terminal) still gets Alembic's normal console
# logging, since nothing sets this attribute in that case.
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name)

# every model in app/models.py, via the shared Base - autogenerate diffs
# against this to propose new migrations
target_metadata = Base.metadata

# SQLite can't ALTER most column properties in place (no native DROP
# COLUMN/ALTER TYPE on older SQLite) - Alembic's "batch mode" works around
# this by recreating the table under the hood. Harmless for Postgres too
# (only engages its special-casing when the dialect actually needs it), so
# it's on unconditionally rather than branching on config.DATABASE_URL.
render_as_batch = True


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=render_as_batch,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata,
            render_as_batch=render_as_batch,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
