"""Tests for os_events DB operations."""

import sqlite3
from capture.db import CaptureDB


class TestOsEventsDB:
    def test_table_created(self, tmp_path):
        db = CaptureDB(str(tmp_path / "test.db"))
        db.connect()

        conn = sqlite3.connect(str(tmp_path / "test.db"))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='os_events'"
        )
        assert cursor.fetchone() is not None
        conn.close()
        db.close()

    def test_insert_and_retrieve(self, tmp_path):
        db = CaptureDB(str(tmp_path / "test.db"))
        db.connect()

        row_id = db.insert_os_event(
            timestamp="2026-03-14T12:00:00+00:00",
            event_type="shell_command",
            source="zsh",
            data="git push origin main",
        )
        assert row_id == 1

        row_id = db.insert_os_event(
            timestamp="2026-03-14T12:01:00+00:00",
            event_type="browser_url",
            source="chrome",
            data="https://github.com",
        )
        assert row_id == 2

        conn = sqlite3.connect(str(tmp_path / "test.db"))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM os_events ORDER BY id").fetchall()
        assert len(rows) == 2
        assert rows[0]["event_type"] == "shell_command"
        assert rows[0]["source"] == "zsh"
        assert rows[0]["data"] == "git push origin main"
        assert rows[1]["event_type"] == "browser_url"
        assert rows[1]["source"] == "chrome"
        conn.close()
        db.close()

    def test_get_last_event_data(self, tmp_path):
        db = CaptureDB(str(tmp_path / "test.db"))
        db.connect()

        assert db.get_last_os_event_data("shell_command", "zsh") is None

        db.insert_os_event(
            timestamp="2026-03-14T12:00:00+00:00",
            event_type="shell_command",
            source="zsh",
            data="first command",
        )
        db.insert_os_event(
            timestamp="2026-03-14T12:01:00+00:00",
            event_type="shell_command",
            source="zsh",
            data="second command",
        )

        assert db.get_last_os_event_data("shell_command", "zsh") == "second command"
        assert db.get_last_os_event_data("browser_url", "chrome") is None

        db.close()
