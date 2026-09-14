"""SQLAlchemy engine / session management for the application database.

This is the app's *own* analytical store where ingested daily dumps are staged.
External systems (SQL Server, MySQL, Postgres, MS Access, ODBC) are treated as
data *sources* and handled by ``app.connectors`` — not here.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()

_connect_args = {}
if settings.app_database_url.startswith("sqlite"):
    # Needed so the SQLite connection can be shared across FastAPI threads.
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.app_database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Imports models so they register with the metadata."""
    from app.models import base  # noqa: F401  (ensures Base is populated)
    from app import models  # noqa: F401  (imports every model module)

    base.Base.metadata.create_all(bind=engine)
