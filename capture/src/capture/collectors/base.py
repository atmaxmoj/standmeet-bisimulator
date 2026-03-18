"""Base class for OS event collectors."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ProbeResult:
    """Result of a collector probe — what was found on this system."""

    available: bool
    source: str
    description: str
    paths: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        status = "OK" if self.available else "SKIP"
        parts = [f"[{status}] {self.source}: {self.description}"]
        for p in self.paths:
            parts.append(f"       path: {p}")
        for w in self.warnings:
            parts.append(f"       warn: {w}")
        return "\n".join(parts)


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

    def probe(self) -> ProbeResult:
        """Probe this system to check if the collector can run.
        Override for richer diagnostics."""
        return ProbeResult(
            available=True,
            source=self.source,
            description=f"{self.source} collector (no probe implemented)",
        )

    def available(self) -> bool:
        """Check if this collector can run. Delegates to probe()."""
        return self.probe().available
