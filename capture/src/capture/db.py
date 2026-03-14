"""SQLite writer for capture frames. Uses WAL for concurrent reads from Docker."""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS frames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    app_name TEXT NOT NULL DEFAULT '',
    window_name TEXT NOT NULL DEFAULT '',
    text TEXT NOT NULL DEFAULT '',
    display_id INTEGER NOT NULL DEFAULT 0,
    image_hash TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_frames_id ON frames(id);
"""


class CaptureDB:
    def __init__(self, path: str):
        self.path = path
        self._conn: sqlite3.Connection | None = None

    def connect(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        logger.debug("connecting to capture DB at %s", self.path)
        self._conn = sqlite3.connect(self.path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)
        self._conn.commit()
        logger.info("capture DB ready at %s (WAL mode)", self.path)

    def close(self):
        if self._conn:
            logger.debug("closing capture DB")
            self._conn.close()

    def insert_frame(
        self,
        timestamp: str,
        app_name: str,
        window_name: str,
        text: str,
        display_id: int,
        image_hash: str,
    ) -> int:
        cursor = self._conn.execute(
            "INSERT INTO frames (timestamp, app_name, window_name, text, display_id, image_hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (timestamp, app_name, window_name, text, display_id, image_hash),
        )
        self._conn.commit()
        row_id = cursor.lastrowid
        logger.debug(
            "inserted frame id=%d display=%d app=%s hash=%s text_len=%d",
            row_id, display_id, app_name, image_hash[:12], len(text),
        )
        return row_id

    def get_last_hash(self, display_id: int) -> str | None:
        cursor = self._conn.execute(
            "SELECT image_hash FROM frames WHERE display_id = ? ORDER BY id DESC LIMIT 1",
            (display_id,),
        )
        row = cursor.fetchone()
        return row[0] if row else None
