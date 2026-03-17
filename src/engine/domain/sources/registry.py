"""SourceRegistry — discover and manage capture sources."""

import logging

from engine.domain.sources.base import CaptureSource

logger = logging.getLogger(__name__)


class SourceRegistry:
    """Central registry for all capture sources."""

    def __init__(self):
        self._sources: dict[str, CaptureSource] = {}

    def register(self, source: CaptureSource):
        """Register a capture source. Overwrites if name already exists."""
        logger.info("Registered capture source: %s", source.name)
        self._sources[source.name] = source

    def get(self, name: str) -> CaptureSource:
        """Get a source by name. Raises KeyError if not found."""
        return self._sources[name]

    def all(self) -> list[CaptureSource]:
        """Return all registered sources."""
        return list(self._sources.values())

    def names(self) -> list[str]:
        """Return all registered source names."""
        return list(self._sources.keys())
