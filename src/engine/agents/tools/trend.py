"""Backwards compatibility — re-exports from pipeline.trend."""

from engine.pipeline.trend import (  # noqa: F401
    get_playbook_history, get_stale_entries, get_similar_entries, make_trend_tools,
)
