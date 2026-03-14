"""Base class for OS event collectors."""

import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """Collects OS events and yields (event_type, source, data) tuples."""

    @property
    @abstractmethod
    def event_type(self) -> str:
        """Event type string, e.g. 'shell_command', 'browser_url'."""

    @property
    @abstractmethod
    def source(self) -> str:
        """Source identifier, e.g. 'zsh', 'chrome'."""

    @abstractmethod
    def collect(self) -> list[str]:
        """Return list of new data entries since last collect.
        Each entry is a single event (one command, one URL, etc.)."""

    def available(self) -> bool:
        """Check if this collector can run on the current system.
        Override to return False if prerequisites are missing."""
        return True
