"""Shell history collectors for macOS (zsh + bash)."""

import logging
import os
from pathlib import Path

from capture.collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class ZshHistoryCollector(BaseCollector):
    """Reads new commands from ~/.zsh_history.

    zsh EXTENDED_HISTORY format: `: <timestamp>:<duration>;<command>`
    Plain format: just the command string.
    """

    event_type = "shell_command"
    source = "zsh"

    def __init__(self):
        self._path = Path.home() / ".zsh_history"
        self._last_size = 0
        self._last_line_count = 0

    def available(self) -> bool:
        return self._path.exists()

    def collect(self) -> list[str]:
        if not self._path.exists():
            return []

        try:
            size = self._path.stat().st_size
            if size <= self._last_size:
                return []  # no new data

            # Read entire file and get new lines
            # zsh_history can have mixed encodings, use errors='replace'
            with open(self._path, "rb") as f:
                raw = f.read()

            lines = raw.decode("utf-8", errors="replace").splitlines()
            if self._last_line_count == 0:
                # First run: just record position, don't dump entire history
                self._last_line_count = len(lines)
                self._last_size = size
                logger.debug("zsh: initialized at %d lines", len(lines))
                return []

            new_lines = lines[self._last_line_count:]
            self._last_line_count = len(lines)
            self._last_size = size

            commands = []
            for line in new_lines:
                cmd = _parse_zsh_line(line)
                if cmd and not _is_noise(cmd):
                    commands.append(cmd)

            if commands:
                logger.debug("zsh: %d new commands", len(commands))
            return commands

        except Exception:
            logger.exception("failed to read zsh history")
            return []


class BashHistoryCollector(BaseCollector):
    """Reads new commands from ~/.bash_history."""

    event_type = "shell_command"
    source = "bash"

    def __init__(self):
        self._path = Path.home() / ".bash_history"
        self._last_size = 0
        self._last_line_count = 0

    def available(self) -> bool:
        return self._path.exists()

    def collect(self) -> list[str]:
        if not self._path.exists():
            return []

        try:
            size = self._path.stat().st_size
            if size <= self._last_size:
                return []

            with open(self._path, "r", errors="replace") as f:
                lines = f.readlines()

            if self._last_line_count == 0:
                self._last_line_count = len(lines)
                self._last_size = size
                logger.debug("bash: initialized at %d lines", len(lines))
                return []

            new_lines = lines[self._last_line_count:]
            self._last_line_count = len(lines)
            self._last_size = size

            commands = []
            for line in new_lines:
                cmd = line.strip()
                if cmd and not _is_noise(cmd):
                    commands.append(cmd)

            if commands:
                logger.debug("bash: %d new commands", len(commands))
            return commands

        except Exception:
            logger.exception("failed to read bash history")
            return []


def _parse_zsh_line(line: str) -> str:
    """Parse a zsh history line. Handles both extended and plain format."""
    line = line.strip()
    if not line:
        return ""
    # Extended format: `: 1234567890:0;actual command`
    if line.startswith(": ") and ";" in line:
        return line.split(";", 1)[1].strip()
    return line


def _is_noise(cmd: str) -> bool:
    """Filter out noisy/trivial commands."""
    trivial = {"ls", "cd", "pwd", "clear", "exit", "history", "l", "ll", "la"}
    first_word = cmd.split()[0] if cmd.split() else ""
    return first_word in trivial
