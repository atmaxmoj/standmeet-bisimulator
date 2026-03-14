"""Get frontmost app and window title using macOS APIs."""

import logging

from AppKit import NSWorkspace
from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGNullWindowID,
    kCGWindowListOptionOnScreenOnly,
)

logger = logging.getLogger(__name__)


def get_frontmost_app() -> tuple[str, str]:
    """
    Return (app_name, window_title) of the frontmost application.
    Falls back to empty strings if unavailable.
    """
    app_name = ""
    window_title = ""

    try:
        workspace = NSWorkspace.sharedWorkspace()
        front_app = workspace.frontmostApplication()
        if front_app:
            app_name = front_app.localizedName() or ""
            pid = front_app.processIdentifier()

            # Get window title from CGWindowList
            window_list = CGWindowListCopyWindowInfo(
                kCGWindowListOptionOnScreenOnly, kCGNullWindowID
            )
            if window_list:
                for window in window_list:
                    if window.get("kCGWindowOwnerPID") == pid:
                        title = window.get("kCGWindowName", "")
                        if title:
                            window_title = title
                            break

    except Exception:
        logger.exception("failed to get frontmost app info")

    logger.debug("frontmost app: %s / %s", app_name, window_title)
    return app_name, window_title
