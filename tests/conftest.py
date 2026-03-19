"""Shared fixtures for engine tests."""

import asyncio
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from engine.storage.db import DB
from engine.storage.models import Base

# Test PostgreSQL connection — uses docker compose db service
TEST_PG_SYNC = "postgresql+psycopg://observer:observer@localhost:15432/observer"
TEST_PG_ASYNC = "postgresql+asyncpg://observer:observer@localhost:15432/observer"


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def _test_schema():
    """Create a unique schema for test isolation, drop after test."""
    schema = f"test_{uuid.uuid4().hex[:8]}"
    engine = create_engine(TEST_PG_SYNC)
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
        conn.commit()
    yield schema
    with engine.connect() as conn:
        conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        conn.commit()
    engine.dispose()


class _TestDB(DB):
    """DB subclass that supports setting search_path via connect_args."""

    def __init__(self, url: str, schema: str):
        super().__init__(url)
        self._schema = schema

    async def connect(self):
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from engine.storage.models import Base
        from sqlalchemy import text as sa_text

        self._engine = create_async_engine(
            self.url, echo=False,
            connect_args={"server_settings": {"search_path": self._schema}},
        )
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self._session_factory = async_sessionmaker(
            bind=self._engine, expire_on_commit=False,
        )


@pytest_asyncio.fixture
async def db(_test_schema):
    """Create a fresh DB for each test using a unique schema."""
    database = _TestDB(TEST_PG_ASYNC, _test_schema)
    await database.connect()
    yield database
    await database.close()


@pytest.fixture
def sync_session(_test_schema):
    """Sync SQLAlchemy session for tests that need it."""
    url = f"{TEST_PG_SYNC}?options=-csearch_path%3D{_test_schema}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    yield session
    session.close()
    engine.dispose()
