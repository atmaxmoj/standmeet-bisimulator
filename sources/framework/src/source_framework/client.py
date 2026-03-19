"""Unified EngineClient — replaces capture/engine_client.py and audio/engine_client.py."""

import json
import logging
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


class EngineClient:
    """HTTP client for pushing source data to the engine API.

    Each source gets an EngineClient configured with its source_name.
    Data is pushed to POST /ingest/{source_name}.
    """

    def __init__(self, base_url: str, source_name: str):
        self.base_url = base_url.rstrip("/")
        self.source_name = source_name

    def _get(self, path: str) -> dict:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                return json.loads(resp.read())
        except Exception:
            return {}

    def _post(self, path: str, data: dict) -> dict:
        url = f"{self.base_url}{path}"
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except urllib.error.URLError as e:
            logger.warning("engine API unreachable (%s): %s", url, e)
            return {}
        except Exception:
            logger.exception("engine API error (%s)", url)
            return {}

    def is_paused(self) -> bool:
        """Check if the pipeline is paused."""
        return self._get("/engine/pipeline").get("paused", False)

    def ingest(self, record: dict) -> int:
        """Push a single record to the engine.

        Args:
            record: Dict with keys matching the source's manifest db.columns.

        Returns:
            Row ID from engine, or 0 on failure.
        """
        result = self._post(f"/ingest/{self.source_name}", record)
        return result.get("id", 0)
