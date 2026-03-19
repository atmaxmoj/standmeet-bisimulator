"""Chrome browser URL source plugin — migrated from capture/collectors/browser_macos.py."""

import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from source_framework.plugin import SourcePlugin, ProbeResult

logger = logging.getLogger(__name__)


def _is_app_running(app_name: str) -> bool:
    """Check if an app is running via AppleScript (without activating it)."""
    try:
        result = subprocess.run(
            ["osascript", "-e",
             f'tell application "System Events" to (name of processes) contains "{app_name}"'],
            capture_output=True, text=True, timeout=3,
        )
        return result.stdout.strip() == "true"
    except Exception:
        return False


class ChromeSource(SourcePlugin):
    """Captures the active Chrome tab URL via AppleScript.

    Works even when Chrome is NOT the frontmost app — we query Chrome
    directly as long as it's running.
    """

    def __init__(self):
        self._last_url = ""

    def probe(self) -> ProbeResult:
        osascript = Path("/usr/bin/osascript")
        if not osascript.exists():
            return ProbeResult(
                available=False,
                source="chrome",
                description="osascript not found (not macOS?)",
                warnings=[f"{osascript} does not exist"],
            )
        return ProbeResult(
            available=True,
            source="chrome",
            description="macOS detected, AppleScript available",
            paths=[str(osascript)],
        )

    def collect(self) -> list[dict]:
        """Return new Chrome URL as a record matching manifest db.columns."""
        try:
            if not _is_app_running("Google Chrome"):
                return []

            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "Google Chrome" to return URL of active tab of front window'],
                capture_output=True, text=True, timeout=3,
            )
            url = result.stdout.strip()
            if not url or url == "missing value" or url == self._last_url:
                return []

            self._last_url = url
            logger.debug("chrome: %s", url)
            return [{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "url": url,
            }]

        except subprocess.TimeoutExpired:
            return []
        except Exception:
            logger.debug("chrome: not running or not accessible")
            return []
