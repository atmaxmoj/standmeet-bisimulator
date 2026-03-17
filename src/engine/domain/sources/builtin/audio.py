"""Audio capture source — microphone transcriptions."""

from engine.domain.entities.frame import Frame
from engine.domain.sources.base import CaptureSource


class AudioSource(CaptureSource):
    @property
    def name(self) -> str:
        return "audio"

    def db_table(self) -> str:
        return "audio_frames"

    def db_schema(self) -> str:
        return """CREATE TABLE IF NOT EXISTS audio_frames (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL, duration_seconds REAL NOT NULL DEFAULT 0.0,
            text TEXT NOT NULL DEFAULT '', language TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'mic', chunk_path TEXT NOT NULL DEFAULT '',
            processed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""

    def db_columns(self) -> list[str]:
        return ["id", "timestamp", "text", "language"]

    def validate_ingest(self, data: dict) -> dict:
        if "timestamp" not in data:
            raise ValueError("Missing required field: timestamp")
        return data

    def to_frame(self, row: dict) -> Frame:
        return Frame(
            id=row["id"], source="audio",
            text=row.get("text") or "", app_name="microphone",
            window_name=f"audio/{row.get('language') or 'unknown'}",
            timestamp=row.get("timestamp") or "",
        )

    def format_context(self, frame: Frame) -> str:
        return f"[{frame.timestamp}] [audio]: {frame.text[:300]}"
