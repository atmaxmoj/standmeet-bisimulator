"""Tests for audio DB operations and migrations."""

import sqlite3
import tempfile
from pathlib import Path

from audio.db import AudioDB


class TestAudioDB:
    def test_create_fresh_db(self, tmp_path):
        db = AudioDB(str(tmp_path / "test.db"))
        db.connect()

        # Should have source column
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        cursor = conn.execute("PRAGMA table_info(audio_frames)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "source" in columns
        conn.close()
        db.close()

    def test_insert_with_source(self, tmp_path):
        db = AudioDB(str(tmp_path / "test.db"))
        db.connect()

        row_id = db.insert_audio_frame(
            timestamp="2026-03-14T12:00:00+00:00",
            duration_seconds=300.0,
            text="Hello world",
            language="en",
            chunk_path="",
            source="mic",
        )
        assert row_id == 1

        row_id = db.insert_audio_frame(
            timestamp="2026-03-14T12:05:00+00:00",
            duration_seconds=300.0,
            text="Speaker output",
            language="en",
            chunk_path="",
            source="speaker",
        )
        assert row_id == 2

        # Verify
        conn = sqlite3.connect(str(tmp_path / "test.db"))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM audio_frames ORDER BY id").fetchall()
        assert len(rows) == 2
        assert rows[0]["source"] == "mic"
        assert rows[1]["source"] == "speaker"
        conn.close()
        db.close()

    def test_default_source_is_mic(self, tmp_path):
        db = AudioDB(str(tmp_path / "test.db"))
        db.connect()

        row_id = db.insert_audio_frame(
            timestamp="2026-03-14T12:00:00+00:00",
            duration_seconds=300.0,
            text="No source specified",
            language="en",
            chunk_path="",
        )

        conn = sqlite3.connect(str(tmp_path / "test.db"))
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT source FROM audio_frames WHERE id = ?", (row_id,)).fetchone()
        assert row["source"] == "mic"
        conn.close()
        db.close()

    def test_migrate_existing_db_without_source(self, tmp_path):
        """Simulate opening a DB that was created before the source column existed."""
        db_path = str(tmp_path / "old.db")

        # Create old-style DB without source column
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE audio_frames (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                duration_seconds REAL NOT NULL DEFAULT 0.0,
                text TEXT NOT NULL DEFAULT '',
                language TEXT NOT NULL DEFAULT '',
                chunk_path TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        conn.execute(
            "INSERT INTO audio_frames (timestamp, duration_seconds, text, language, chunk_path) "
            "VALUES (?, ?, ?, ?, ?)",
            ("2026-03-14T12:00:00", 300.0, "Old entry", "en", ""),
        )
        conn.commit()
        conn.close()

        # Open with AudioDB — should auto-migrate
        db = AudioDB(db_path)
        db.connect()

        # Old row should have default source='mic'
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT source FROM audio_frames WHERE id = 1").fetchone()
        assert row["source"] == "mic"

        # New inserts should work with source
        db.insert_audio_frame(
            timestamp="2026-03-14T12:05:00",
            duration_seconds=300.0,
            text="New entry",
            language="en",
            chunk_path="",
            source="speaker",
        )
        row = conn.execute("SELECT source FROM audio_frames WHERE id = 2").fetchone()
        assert row["source"] == "speaker"

        conn.close()
        db.close()
