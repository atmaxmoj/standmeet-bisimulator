"""SourcePlugin ABC — the interface every source must implement."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ProbeResult:
    """Result of a source probe — what was found on this system."""

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


class SourcePlugin(ABC):
    """Base class for all source plugins.

    Implement probe() and collect() at minimum.
    Override start() for custom behavior (audio streaming, log tailing, etc.).
    """

    @abstractmethod
    def probe(self) -> ProbeResult:
        """Check if this source can run on the current system.

        Called before start(). If not available, the source is skipped.
        """

    @abstractmethod
    def collect(self) -> list[dict]:
        """One collection cycle.

        Return a list of records with keys matching manifest db.columns.
        Called repeatedly by the default start() loop.
        """

    def start(self, client: "EngineClient", config: dict):
        """Default poll loop. Override for custom behavior (audio, oslog).

        Args:
            client: EngineClient for pushing data to engine.
            config: Merged config (manifest defaults + user overrides).
        """
        import time

        interval = config.get("interval_seconds", 3)
        while True:
            if client.is_paused():
                time.sleep(interval)
                continue
            records = self.collect()
            for record in records:
                client.ingest(record)
            time.sleep(interval)


# Avoid circular import — EngineClient is passed as a runtime dependency.
# The type hint is a string forward reference.
