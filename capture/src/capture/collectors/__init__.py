"""OS event collectors: shell history, browser URLs, clipboard."""

import sys
from capture.collectors.base import BaseCollector

if sys.platform == "darwin":
    from capture.collectors.shell_macos import ZshHistoryCollector, BashHistoryCollector
    from capture.collectors.browser_macos import SafariURLCollector, ChromeURLCollector

    def get_all_collectors() -> list[BaseCollector]:
        return [
            ZshHistoryCollector(),
            BashHistoryCollector(),
            SafariURLCollector(),
            ChromeURLCollector(),
        ]

elif sys.platform == "win32":
    from capture.collectors.shell_windows import PowerShellHistoryCollector, GitBashHistoryCollector
    from capture.collectors.browser_windows import ChromeURLCollector as WinChromeURLCollector, EdgeURLCollector

    def get_all_collectors() -> list[BaseCollector]:
        return [
            PowerShellHistoryCollector(),
            GitBashHistoryCollector(),
            WinChromeURLCollector(),
            EdgeURLCollector(),
        ]

else:
    def get_all_collectors() -> list[BaseCollector]:
        return []
