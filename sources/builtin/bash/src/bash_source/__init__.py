"""Bash shell history source plugin — migrated from capture/collectors/shell_macos.py."""

import logging
from datetime import datetime, timezone
from pathlib import Path

from source_framework.plugin import SourcePlugin, ProbeResult

logger = logging.getLogger(__name__)

_NOISE_COMMANDS = {"ls", "cd", "pwd", "clear", "exit", "history", "l", "ll", "la"}


def _is_noise(cmd: str) -> bool:
    """Filter out noisy/trivial commands."""
    first_word = cmd.split()[0] if cmd.split() else ""
    return first_word in _NOISE_COMMANDS


class _HistoryFileTracker:
    """Tracks ~/.bash_history for new lines."""

    def __init__(self, path: Path):
        self.path = path
        self._last_size = 0
        self._last_line_count = 0

    def collect_new(self) -> list[str]:
        if not self.path.exists():
            return []
        try:
            size = self.path.stat().st_size
            if size <= self._last_size:
                return []

            with open(self.path, "rb") as f:
                raw = f.read()
            lines = raw.decode("utf-8", errors="replace").splitlines()

            # First read: snapshot current position, don't emit anything.
            if self._last_line_count == 0:
                self._last_line_count = len(lines)
                self._last_size = size
                return []

            if len(lines) <= self._last_line_count:
                return []

            new_lines = lines[self._last_line_count:]
            self._last_line_count = len(lines)
            self._last_size = size

            commands = []
            for line in new_lines:
                cmd = line.strip()
                if cmd and not _is_noise(cmd):
                    commands.append(cmd)
            return commands
        except Exception:
            logger.exception("failed to read %s", self.path)
            return []


class BashSource(SourcePlugin):
    """Captures new commands from ~/.bash_history."""

    def __init__(self, home: Path | None = None):
        self._home = home or Path.home()
        self._path = self._home / ".bash_history"
        self._tracker: _HistoryFileTracker | None = None

    def probe(self) -> ProbeResult:
        if not self._path.exists():
            return ProbeResult(
                available=False,
                source="bash",
                description="no history file found",
                warnings=["checked ~/.bash_history"],
            )
        warnings = []
        if self._path.stat().st_size == 0:
            warnings.append("~/.bash_history is empty")
        return ProbeResult(
            available=True,
            source="bash",
            description="found ~/.bash_history",
            paths=[str(self._path)],
            warnings=warnings,
        )

    def collect(self) -> list[dict]:
        """Return new commands as records matching manifest db.columns."""
        if not self._path.exists():
            return []
        if self._tracker is None:
            self._tracker = _HistoryFileTracker(self._path)
        records = []
        timestamp = datetime.now(timezone.utc).isoformat()
        for cmd in self._tracker.collect_new():
            records.append({
                "timestamp": timestamp,
                "command": cmd,
            })
        return records
