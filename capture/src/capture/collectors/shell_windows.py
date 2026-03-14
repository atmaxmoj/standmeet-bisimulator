"""Shell history collector for Windows (PowerShell)."""

import logging
import os
from pathlib import Path

from capture.collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class PowerShellHistoryCollector(BaseCollector):
    """Reads new commands from PowerShell ConsoleHost_history.txt."""

    event_type = "shell_command"
    source = "powershell"

    def __init__(self):
        # Standard PowerShell history location
        appdata = os.environ.get("APPDATA", "")
        self._path = Path(appdata) / "Microsoft" / "Windows" / "PowerShell" / "PSReadLine" / "ConsoleHost_history.txt"
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
                logger.debug("powershell: initialized at %d lines", len(lines))
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
                logger.debug("powershell: %d new commands", len(commands))
            return commands

        except Exception:
            logger.exception("failed to read PowerShell history")
            return []


def _is_noise(cmd: str) -> bool:
    """Filter out trivial commands."""
    trivial = {"ls", "cd", "pwd", "cls", "clear", "exit", "dir", "history", "Get-History"}
    first_word = cmd.split()[0] if cmd.split() else ""
    return first_word in trivial
