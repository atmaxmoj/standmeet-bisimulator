import logging

import aiosqlite
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary TEXT NOT NULL,
    app_names TEXT NOT NULL DEFAULT '',
    frame_count INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    ended_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS playbook_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    context TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.0,
    maturity TEXT NOT NULL DEFAULT 'nascent',
    evidence TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class DB:
    def __init__(self, path: str):
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self):
        logger.debug("connecting to database at %s", self.path)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()
        logger.info("database connected and schema initialized at %s", self.path)

    async def close(self):
        if self._conn:
            logger.debug("closing database connection")
            await self._conn.close()

    # -- state (each collector tracks its own cursor) --

    async def get_state(self, key: str, default: int = 0) -> int:
        async with self._conn.execute(
            "SELECT value FROM state WHERE key = ?", (key,)
        ) as cur:
            row = await cur.fetchone()
            val = int(row["value"]) if row else default
            logger.debug("get_state(%s) = %d", key, val)
            return val

    async def set_state(self, key: str, value: int):
        await self._conn.execute(
            "INSERT INTO state (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        await self._conn.commit()
        logger.debug("set_state(%s) = %d", key, value)

    # -- episodes --

    async def insert_episode(
        self,
        summary: str,
        app_names: str,
        frame_count: int,
        started_at: str,
        ended_at: str,
    ) -> int:
        async with self._conn.execute(
            "INSERT INTO episodes (summary, app_names, frame_count, started_at, ended_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (summary, app_names, frame_count, started_at, ended_at),
        ) as cur:
            await self._conn.commit()
            logger.debug(
                "inserted episode id=%d frame_count=%d range=[%s, %s]",
                cur.lastrowid, frame_count, started_at, ended_at,
            )
            return cur.lastrowid

    async def get_recent_episodes(self, days: int = 7) -> list[dict]:
        cutoff = datetime.now(timezone.utc).isoformat()
        async with self._conn.execute(
            "SELECT * FROM episodes WHERE created_at >= datetime('now', ?) ORDER BY created_at",
            (f"-{days} days",),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def get_all_episodes(self, limit: int = 100, offset: int = 0) -> list[dict]:
        async with self._conn.execute(
            "SELECT * FROM episodes ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    # -- playbook entries --

    async def upsert_playbook(
        self,
        name: str,
        context: str,
        action: str,
        confidence: float,
        evidence: str,
        maturity: str = "nascent",
    ):
        await self._conn.execute(
            "INSERT INTO playbook_entries (name, context, action, confidence, maturity, evidence, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now')) "
            "ON CONFLICT(name) DO UPDATE SET "
            "context=excluded.context, action=excluded.action, "
            "confidence=excluded.confidence, maturity=excluded.maturity, "
            "evidence=excluded.evidence, "
            "updated_at=datetime('now')",
            (name, context, action, confidence, maturity, evidence),
        )
        await self._conn.commit()
        logger.debug(
            "upserted playbook name=%s confidence=%.2f maturity=%s",
            name, confidence, maturity,
        )

    async def get_all_playbooks(self) -> list[dict]:
        async with self._conn.execute(
            "SELECT * FROM playbook_entries ORDER BY confidence DESC"
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    # -- stats --

    async def get_status(self) -> dict:
        episode_count = 0
        playbook_count = 0
        async with self._conn.execute("SELECT COUNT(*) as c FROM episodes") as cur:
            row = await cur.fetchone()
            episode_count = row["c"]
        async with self._conn.execute(
            "SELECT COUNT(*) as c FROM playbook_entries"
        ) as cur:
            row = await cur.fetchone()
            playbook_count = row["c"]
        return {
            "episode_count": episode_count,
            "playbook_count": playbook_count,
        }
