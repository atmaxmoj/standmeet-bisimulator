"""Session utilities — convert raw connections to SQLAlchemy sessions."""

import sqlite3

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from engine.storage.models import Base

_cache: dict[int, sessionmaker] = {}


def get_session(conn: sqlite3.Connection) -> Session:
    """Wrap a raw sqlite3.Connection in a SQLAlchemy Session.

    Caches the engine per connection id to avoid recreating on every call.
    """
    conn_id = id(conn)
    if conn_id not in _cache:
        engine = create_engine("sqlite://", creator=lambda: conn)
        Base.metadata.create_all(engine)
        _cache[conn_id] = sessionmaker(bind=engine)
    return _cache[conn_id]()
