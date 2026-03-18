"""Backwards compatibility — re-exports from pipeline.dedup."""

from engine.pipeline.dedup import (  # noqa: F401
    find_similar_pairs, merge_entries, make_dedup_tools,
)
