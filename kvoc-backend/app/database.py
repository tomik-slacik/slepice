from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import declarative_base, sessionmaker

from . import config

engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=engine)
Base = declarative_base()

# The very first migration Alembic ever got for this project - see
# migrations/versions/24190d4fa3db_baseline.py. It creates exactly what
# Base.metadata.create_all() used to produce, nothing more - it's the
# stamping target for a database that already has tables but has never run
# through Alembic (see init_db() below), not a real schema change.
_BASELINE_REVISION = "24190d4fa3db"


def get_db():
    """FastAPI dependency: one DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Brings the database schema up to date via real Alembic migrations
    (see migrations/) - every table, index and column any model currently
    declares, plus a real history of how it got there. Runs on every boot,
    same as the old Base.metadata.create_all() this replaced; still zero
    manual steps for local dev (`python run.py` just works), but now also
    correct for a real deployment with real data already in it, which
    create_all() alone never was (it can create a missing *table*, but it
    can't add a column to one that already exists, rename anything, or
    change a type).

    Three cases, told apart by what's already in the target database:
      1. Completely empty (no tables at all) - straightforward, `upgrade
         head` runs every migration from the beginning and creates
         everything.
      2. Has tables, but no `alembic_version` row - a database that was
         created before Alembic existed in this project (by the old
         create_all()-only path). Stamping it at the baseline revision
         (see _BASELINE_REVISION above) tells Alembic "the baseline
         migration's effects already happened, don't try to re-run its
         CREATE TABLEs" without touching a single row of real data: then
         `upgrade head` applies only whatever came *after* baseline (e.g.
         the FK-index/updated_at migration) on top of what's actually
         there.
      3. Already has an `alembic_version` row - a database Alembic has
         already been managing. `upgrade head` just applies anything new
         since last boot, same as any other migration-managed app.
    """
    from alembic import command
    from alembic.config import Config as AlembicConfig
    from alembic.runtime.migration import MigrationContext

    from . import models  # noqa: F401  (import registers every model on Base first)

    alembic_ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    alembic_cfg = AlembicConfig(str(alembic_ini))
    alembic_cfg.set_main_option("script_location", str(alembic_ini.parent / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", config.DATABASE_URL)
    alembic_cfg.attributes["configure_logger"] = False  # don't let Alembic reconfigure this app's own logging

    with engine.connect() as conn:
        current_rev = MigrationContext.configure(conn).get_current_revision()
        pre_alembic_db = current_rev is None and inspect(conn).has_table("users")

    if pre_alembic_db:
        command.stamp(alembic_cfg, _BASELINE_REVISION)
    command.upgrade(alembic_cfg, "head")
