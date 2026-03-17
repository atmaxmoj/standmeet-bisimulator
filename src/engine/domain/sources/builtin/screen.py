"""Screen capture source — OCR text from screen recordings."""

from engine.domain.entities.frame import Frame
from engine.domain.sources.base import CaptureSource


class ScreenSource(CaptureSource):
    @property
    def name(self) -> str:
        return "screen"

    def db_table(self) -> str:
        return "frames"

    def db_schema(self) -> str:
        return """CREATE TABLE IF NOT EXISTS frames (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL, app_name TEXT NOT NULL DEFAULT '',
            window_name TEXT NOT NULL DEFAULT '', text TEXT NOT NULL DEFAULT '',
            display_id INTEGER NOT NULL DEFAULT 0, image_hash TEXT NOT NULL DEFAULT '',
            image_path TEXT NOT NULL DEFAULT '', processed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )"""

    def db_columns(self) -> list[str]:
        return ["id", "timestamp", "app_name", "window_name", "text", "image_path"]

    def validate_ingest(self, data: dict) -> dict:
        if "timestamp" not in data:
            raise ValueError("Missing required field: timestamp")
        return data

    def to_frame(self, row: dict) -> Frame:
        return Frame(
            id=row["id"], source="capture",
            text=row.get("text") or "", app_name=row.get("app_name") or "",
            window_name=row.get("window_name") or "",
            timestamp=row.get("timestamp") or "",
            image_path=row.get("image_path") or "",
        )

    def format_context(self, frame: Frame) -> str:
        text = frame.text[:300].replace("\n", " ")
        return f"[{frame.timestamp}] {frame.app_name}/{frame.window_name}[capture]: {text}"
