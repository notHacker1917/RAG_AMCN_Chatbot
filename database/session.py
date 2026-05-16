"""
SQLAlchemy engine + session management.

`Base` is the declarative base used by ORM models in `models.py`.
`init_db()` creates tables if they don't exist.
`get_session()` is a context-manager that handles commit/rollback.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Declarative base for ORM models."""


# Connect args: SQLite needs check_same_thread=False for Flask threads
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    echo=settings.db_echo,
    future=True,
    connect_args=_connect_args,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)


def init_db() -> None:
    """Import ORM models then create all tables."""
    # IMPORTANT: import models for side-effects (table registration)
    from database import models  # noqa: F401

    logger.info("Creating database schema (if missing)…")
    Base.metadata.create_all(bind=engine)
    logger.info("Schema ready.")


@contextmanager
def get_session() -> Iterator[Session]:
    """Yield a SQLAlchemy session; commit on success, rollback on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
