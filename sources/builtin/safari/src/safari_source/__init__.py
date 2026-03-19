"""Safari browser URL source plugin — migrated from capture/collectors/browser_macos.py."""

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


class SafariSource(SourcePlugin):
    """Captures active Safari tab URLs via AppleScript.

    Works even when Safari is NOT the frontmost app — we query Safari
    directly as long as it's running.
    """

    def __init__(self):
        self._last_url = ""

    def probe(self) -> ProbeResult:
        osascript = Path("/usr/bin/osascript")
        if not osascript.exists():
            return ProbeResult(
                available=False,
                source="safari",
                description="osascript not found (not macOS)",
                warnings=[f"expected {osascript}"],
            )

        return ProbeResult(
            available=True,
            source="safari",
            description="osascript available, can query Safari tabs",
            paths=[str(osascript)],
        )

    def collect(self) -> list[dict]:
        """Return new Safari URLs as records matching manifest db.columns."""
        try:
            if not _is_app_running("Safari"):
                return []

            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "Safari" to return URL of current tab of front window'],
                capture_output=True, text=True, timeout=3,
            )
            url = result.stdout.strip()
            if not url or url == "missing value" or url == self._last_url:
                return []

            self._last_url = url
            logger.debug("safari: %s", url)
            return [{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "url": url,
            }]

        except subprocess.TimeoutExpired:
            return []
        except Exception:
            logger.debug("safari: not running or not accessible")
            return []
