"""OS event source — shell commands, browser URLs."""

from engine.domain.entities.frame import Frame
from engine.domain.sources.base import CaptureSource


class OsEventSource(CaptureSource):
    @property
    def name(self) -> str:
        return "os_event"

    def db_table(self) -> str:
        return "os_events"

    def db_schema(self) -> str:
        return """CREATE TABLE IF NOT EXISTS os_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL, event_type TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT '', data TEXT NOT NULL DEFAULT '',
            processed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""

    def db_columns(self) -> list[str]:
        return ["id", "timestamp", "event_type", "source", "data"]

    def validate_ingest(self, data: dict) -> dict:
        if "timestamp" not in data:
            raise ValueError("Missing required field: timestamp")
        if "event_type" not in data:
            raise ValueError("Missing required field: event_type")
        return data

    def to_frame(self, row: dict) -> Frame:
        return Frame(
            id=row["id"], source="os_event",
            text=row.get("data") or "", app_name=row.get("event_type") or "",
            window_name=row.get("source") or "",
            timestamp=row.get("timestamp") or "",
        )

    def format_context(self, frame: Frame) -> str:
        return f"[{frame.timestamp}] [os_event/{frame.app_name}]: {frame.text[:300]}"
