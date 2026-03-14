import os
from pathlib import Path

DB_PATH = os.environ.get(
    "CAPTURE_DB_PATH",
    str(Path.home() / ".bisimulator" / "capture.db"),
)

CAPTURE_INTERVAL = int(os.environ.get("CAPTURE_INTERVAL", "3"))

LOG_LEVEL = os.environ.get("LOG_LEVEL", "DEBUG").upper()
