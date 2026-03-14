"""Rules-based signal filter. No LLM, $0 cost.

Only does noise removal. Task boundary detection is Haiku's job.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from engine.pipeline.collector import Frame

logger = logging.getLogger(__name__)

# Apps that produce noise, not signal
IGNORE_APPS = frozenset(
    {
        "Finder",
        "SystemUIServer",
        "Dock",
        "loginwindow",
        "Spotlight",
        "NotificationCenter",
        "Control Center",
        "WindowManager",
        "ScreenSaverEngine",
    }
)

MIN_TEXT_LENGTH = 10


def should_keep(frame: Frame) -> bool:
    # Audio frames always pass through (already transcribed, no noise filtering needed)
    if frame.source == "audio":
        if not frame.text or not frame.text.strip():
            logger.debug("filtered out audio frame id=%d (empty text)", frame.id)
            return False
        return True
    if frame.app_name in IGNORE_APPS:
        logger.debug("filtered out frame id=%d app=%s (ignored app)", frame.id, frame.app_name)
        return False
    if not frame.text or len(frame.text.strip()) < MIN_TEXT_LENGTH:
        logger.debug("filtered out frame id=%d app=%s (text too short: %d chars)", frame.id, frame.app_name, len(frame.text.strip()) if frame.text else 0)
        return False
    return True


@dataclass
class WindowAccumulator:
    """
    Accumulates frames in fixed time windows.
    Emits a window of frames every `window_minutes` OR when idle gap detected.
    Haiku decides where the task boundaries are within each window.
    """

    window_minutes: int = 30
    idle_threshold_seconds: int = 300

    _buffer: list[Frame] = field(default_factory=list)

    def feed(self, frames: list[Frame]) -> list[list[Frame]]:
        """
        Feed new frames. Returns completed windows (each = list of filtered frames).
        A window closes when:
          - Time span of buffer exceeds window_minutes
          - Idle gap > idle_threshold between frames (user went AFK)
        """
        completed: list[list[Frame]] = []

        for frame in frames:
            if not should_keep(frame):
                continue

            # Check idle gap -> flush buffer
            if self._buffer and self._idle_gap(self._buffer[-1], frame):
                logger.debug(
                    "idle gap detected between frame id=%d and id=%d, flushing %d frames",
                    self._buffer[-1].id, frame.id, len(self._buffer),
                )
                completed.append(self._buffer)
                self._buffer = []

            self._buffer.append(frame)

            # Check window duration -> flush buffer
            if self._window_exceeded():
                logger.debug(
                    "window time exceeded (%d min), flushing %d frames",
                    self.window_minutes, len(self._buffer),
                )
                completed.append(self._buffer)
                self._buffer = []

        logger.debug(
            "feed: received %d frames, kept %d in buffer, emitted %d windows",
            len(frames), len(self._buffer), len(completed),
        )
        return completed

    def flush(self) -> list[Frame] | None:
        """Force-flush the current buffer (e.g. on shutdown)."""
        if self._buffer:
            logger.debug("flush: emitting remaining %d frames", len(self._buffer))
            buf = self._buffer
            self._buffer = []
            return buf
        logger.debug("flush: buffer empty, nothing to emit")
        return None

    def _idle_gap(self, prev: Frame, curr: Frame) -> bool:
        try:
            t_prev = datetime.fromisoformat(prev.timestamp)
            t_curr = datetime.fromisoformat(curr.timestamp)
            return (t_curr - t_prev) > timedelta(seconds=self.idle_threshold_seconds)
        except (ValueError, TypeError):
            return False

    def _window_exceeded(self) -> bool:
        if len(self._buffer) < 2:
            return False
        try:
            t_start = datetime.fromisoformat(self._buffer[0].timestamp)
            t_end = datetime.fromisoformat(self._buffer[-1].timestamp)
            return (t_end - t_start) > timedelta(minutes=self.window_minutes)
        except (ValueError, TypeError):
            return False
