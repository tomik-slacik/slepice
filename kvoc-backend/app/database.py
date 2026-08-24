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
    gained a new column (e.g. users.fcm_token, farms.lat) would otherwise
    make every query against that column fail. There's no Alembic here
    (deliberately - this project has no real deployed user data yet, see
    docs/DEPLOYMENT.md), so this is a tiny, idempotent stand-in: for each
    (table, column, SQL type) the current models expect, add it if the
    actual table doesn't have it yet.
    """
    from sqlalchemy import inspect

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    wanted = [
        ("users", "fcm_token", "VARCHAR"),
        ("farms", "lat", "FLOAT"),
        ("farms", "lng", "FLOAT"),
        ("farms", "weekly_capacity", "INTEGER"),
    ]
    for table, column, sql_type in wanted:
        if table not in existing_tables:
            continue  # fresh DB - create_all above just made it with every column
        existing_cols = {c["name"] for c in inspector.get_columns(table)}
        if column not in existing_cols:
            with engine.begin() as conn:
                conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type}")
