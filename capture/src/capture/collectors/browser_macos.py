"""Browser URL collectors for macOS using AppleScript."""

import logging
import subprocess

from capture.collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class SafariURLCollector(BaseCollector):
    """Gets the active Safari tab URL via AppleScript."""

    event_type = "browser_url"
    source = "safari"

    def __init__(self):
        self._last_url = ""

    def available(self) -> bool:
        # Safari is always available on macOS
        return True

    def collect(self) -> list[str]:
        try:
            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to set frontApp to name of first application process whose frontmost is true\n'
                 'if frontApp is "Safari" then\n'
                 '  tell application "Safari" to return URL of current tab of front window\n'
                 'else\n'
                 '  return ""\n'
                 'end if'],
                capture_output=True, text=True, timeout=3,
            )
            url = result.stdout.strip()
            if not url or url == self._last_url:
                return []

            self._last_url = url
            logger.debug("safari: %s", url)
            return [url]

        except subprocess.TimeoutExpired:
            return []
        except Exception:
            logger.debug("safari: not running or not accessible")
            return []


class ChromeURLCollector(BaseCollector):
    """Gets the active Chrome tab URL via AppleScript."""

    event_type = "browser_url"
    source = "chrome"

    def __init__(self):
        self._last_url = ""

    def available(self) -> bool:
        return True

    def collect(self) -> list[str]:
        try:
            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to set frontApp to name of first application process whose frontmost is true\n'
                 'if frontApp is "Google Chrome" then\n'
                 '  tell application "Google Chrome" to return URL of active tab of front window\n'
                 'else\n'
                 '  return ""\n'
                 'end if'],
                capture_output=True, text=True, timeout=3,
            )
            url = result.stdout.strip()
            if not url or url == self._last_url:
                return []

            self._last_url = url
            logger.debug("chrome: %s", url)
            return [url]

        except subprocess.TimeoutExpired:
            return []
        except Exception:
            logger.debug("chrome: not running or not accessible")
            return []
