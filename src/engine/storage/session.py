"""Session + time utilities for cross-database compatibility."""

import sqlite3
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine as _sa_create_engine
from sqlalchemy.orm import Session, sessionmaker

from engine.storage.models import Base
from engine.config import Settings

_factory_cache: dict[str, sessionmaker] = {}


def get_session(conn_or_url) -> Session:
    """Get a SQLAlchemy Session.

    Accepts:
    - sqlite3.Connection: wraps it via creator
    - str (URL): creates engine from URL
    - psycopg.Connection: uses database_url_sync from settings
    """
    if isinstance(conn_or_url, str):
        url = conn_or_url
    elif isinstance(conn_or_url, sqlite3.Connection):
        # SQLite: wrap raw connection via creator
        conn_id = id(conn_or_url)
        cache_key = f"sqlite_{conn_id}"
        if cache_key not in _factory_cache:
            engine = _sa_create_engine("sqlite://", creator=lambda: conn_or_url)
            Base.metadata.create_all(engine)
            _factory_cache[cache_key] = sessionmaker(bind=engine)
        return _factory_cache[cache_key]()
    else:
        # psycopg or other: use settings URL
        url = Settings().database_url_sync

    if url not in _factory_cache:
        kwargs = {}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
        engine = _sa_create_engine(url, **kwargs)
        Base.metadata.create_all(engine)
        _factory_cache[url] = sessionmaker(bind=engine)
    return _factory_cache[url]()


def ago(days: int = 0, hours: int = 0) -> str:
    """Return ISO timestamp for N days/hours ago. Cross-database compatible."""
    dt = datetime.now(timezone.utc) - timedelta(days=days, hours=hours)
    return dt.isoformat()
