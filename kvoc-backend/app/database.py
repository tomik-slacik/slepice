from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from . import config

engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=True, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: one DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401  (import registers the models on Base before create_all)

    Base.metadata.create_all(bind=engine)
    _add_missing_columns()


def _add_missing_columns() -> None:
    """Base.metadata.create_all only creates missing *tables*, never adds a
    column to a table that already exists - so a DB created before a model
    gained a new column (e.g. users.fcm_token) would otherwise make every
    query against that column fail. There's no Alembic here (deliberately -
    this project has no real deployed user data yet, see docs/DEPLOYMENT.md),
    so this is a tiny, idempotent stand-in: add any column the model expects
    but the actual table doesn't have yet, using its declared type.
    """
    from sqlalchemy import inspect

    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return  # fresh DB - create_all above just made it with every column
    existing_cols = {c["name"] for c in inspector.get_columns("users")}
    if "fcm_token" not in existing_cols:
        with engine.begin() as conn:
            conn.exec_driver_sql("ALTER TABLE users ADD COLUMN fcm_token VARCHAR")
