"""macOS os_log source plugin — streams system events via `log stream`.

Runs `log stream --style json --predicate '...'` as a subprocess,
parses JSON output incrementally with ijson, classifies events into categories:
- app_launch, app_quit, frontmost_change
- sleep, wake, lock, unlock

This is a custom start() source (streaming subprocess) — it overrides the
default poll loop since it needs a background thread for the JSON stream.
"""

import logging
import subprocess
import threading
import time
from collections import deque
from pathlib import Path

from source_framework.plugin import SourcePlugin, ProbeResult

logger = logging.getLogger(__name__)

# Predicate for useful system events
PREDICATE = (
    '(subsystem == "com.apple.runningboard") OR '
    '(process == "powerd" AND eventMessage CONTAINS "sleepWake") OR '
    '(process == "loginwindow")'
)


# ── Event classification ─────────────────────────────────────────────


def _classify_runningboard(msg: str) -> str | None:
    if "frontmost" in msg.lower():
        return "frontmost_change"
    # "Now tracking process:" is the actual launch signal
    if "Now tracking process" in msg:
        return "app_launch"
    if "termination reported" in msg or "process exited" in msg:
        return "app_quit"
    return None


def _classify_power(msg: str) -> str | None:
    if "sleepWake" in msg or "Sleep" in msg:
        return "sleep"
    if "Wake" in msg:
        return "wake"
    return None


def _classify_loginwindow(msg: str) -> str | None:
    msg_lower = msg.lower()
    if "unlock" in msg_lower:
        return "unlock"
    if "lock" in msg_lower:
        return "lock"
    return None


def classify_event(entry: dict) -> str | None:
    """Classify an os_log entry into a category. Returns None if not useful."""
    msg = entry.get("eventMessage", "")
    process_path = entry.get("processImagePath", "")

    if entry.get("subsystem") == "com.apple.runningboard":
        return _classify_runningboard(msg)
    if "powerd" in process_path:
        return _classify_power(msg)
    if "loginwindow" in process_path:
        return _classify_loginwindow(msg)
    return None


def format_event(entry: dict, category: str) -> str:
    """Format an os_log entry into a human-readable string for storage."""
    msg = entry.get("eventMessage", "")
    process = entry.get("processImagePath", "").rsplit("/", 1)[-1]
    return f"[{category}] {process}: {msg[:300]}"


# ── Stream helpers ────────────────────────────────────────────────────


class _ByteStreamAdapter:
    """Wraps a text or bytes stream into a bytes stream for ijson.

    Skips everything before the first '[' (log stream prints a
    'Filtering...' line before the JSON array).
    """

    def __init__(self, stream):
        self._stream = stream
        self._found = False
        self._leftover = b""

    def read(self, size=4096):
        if self._leftover:
            out = self._leftover[:size]
            self._leftover = self._leftover[size:]
            return out

        chunk = self._stream.read(size)
        if not chunk:
            return b""
        if isinstance(chunk, str):
            chunk = chunk.encode("utf-8")

        if not self._found:
            idx = chunk.find(b"[")
            if idx == -1:
                return self.read(size)  # skip, try next chunk
            self._found = True
            chunk = chunk[idx:]

        return chunk


def _skip_until_bracket(stream):
    """Wrap a stream to skip bytes until the first '[' character."""
    return _ByteStreamAdapter(stream)


# ── OsLogSource plugin ───────────────────────────────────────────────


class OsLogSource(SourcePlugin):
    """Streams macOS os_log events via `log stream` subprocess.

    A background thread reads the subprocess stdout, parses JSON with ijson,
    classifies events, and buffers them. The custom start() loop drains the
    buffer via collect() and pushes records to the engine via client.ingest().
    """

    def __init__(self, command: list[str] | None = None, stdin=None):
        self._command = command or [
            "log", "stream", "--style", "json", "--level", "info",
            "--predicate", PREDICATE,
        ]
        self._stdin = stdin  # For testing: read from stdin instead of subprocess
        self._buffer: deque[tuple[str, str, str]] = deque(maxlen=1000)
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._started = False

    def probe(self) -> ProbeResult:
        """Check if /usr/bin/log exists (macOS only)."""
        log_path = Path("/usr/bin/log")
        if not log_path.exists():
            return ProbeResult(
                available=False,
                source="oslog",
                description="log command not found (not macOS?)",
            )
        return ProbeResult(
            available=True,
            source="oslog",
            description="os_log stream via /usr/bin/log",
            paths=[str(log_path)],
        )

    def _reader(self, stream):
        """Background thread: stream-parse JSON array using ijson.

        `log stream --style json` outputs a JSON array. ijson yields
        each object incrementally as it's parsed — no buffering needed.
        The first line may be a "Filtering..." text which we skip by
        wrapping in a filter that drops non-JSON prefix bytes.
        """
        import ijson

        # log stream prefixes output with a "Filtering..." line before the JSON.
        # Wrap the stream to skip bytes until we see '['.
        byte_stream = _skip_until_bracket(stream)

        try:
            for entry in ijson.items(byte_stream, "item"):
                category = classify_event(entry)
                if category is None:
                    continue
                timestamp = entry.get("timestamp", "")
                data = format_event(entry, category)
                self._buffer.append((timestamp, category, data))
        except Exception:
            logger.debug("os_log: ijson stream ended or errored")

    def _start_reader(self):
        """Start the subprocess and background reader thread."""
        if self._started:
            return
        self._started = True

        if self._stdin is not None:
            # Test mode: read from provided stream
            self._thread = threading.Thread(
                target=self._reader, args=(self._stdin,), daemon=True,
            )
            self._thread.start()
            return

        try:
            self._proc = subprocess.Popen(
                self._command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            self._thread = threading.Thread(
                target=self._reader, args=(self._proc.stdout,), daemon=True,
            )
            self._thread.start()
            logger.info("os_log stream started (pid %d)", self._proc.pid)
        except Exception:
            logger.exception("failed to start log stream")

    def collect(self) -> list[dict]:
        """Drain the buffer and return records matching manifest db.columns."""
        records = []
        while self._buffer:
            timestamp, category, data = self._buffer.popleft()
            records.append({
                "timestamp": timestamp,
                "category": category,
                "data": data,
            })
        return records

    def start(self, client, config: dict):
        """Custom start loop — runs the subprocess reader, then polls collect().

        Overrides the default poll loop because os_log uses a streaming
        subprocess with a background reader thread rather than simple polling.
        """
        self._start_reader()

        interval = config.get("interval_seconds", 2)
        while True:
            if client.is_paused():
                time.sleep(interval)
                continue
            records = self.collect()
            for record in records:
                client.ingest(record)
            time.sleep(interval)
