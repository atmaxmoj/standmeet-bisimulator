"""Playbook deduplication tools for the GC agent.

Layer 3 (garbage collection): provides tools for the GC agent to find
and merge similar entries. The agent decides what to merge — we don't
auto-merge on Jaccard alone.
"""

import json
import logging
import sqlite3

from engine.infra.llm import ToolDef

logger = logging.getLogger(__name__)


def find_similar_pairs(conn: sqlite3.Connection, threshold: float = 0.8) -> list[dict]:
    """Find pairs of playbook entries with Jaccard similarity > threshold.

    Jaccard similarity is computed on the set of hyphen-split words in the name.
    """
    rows = conn.execute(
        "SELECT id, name, confidence, maturity, context FROM playbook_entries ORDER BY confidence DESC"
    ).fetchall()

    entries = [(dict(r), set(r["name"].split("-"))) for r in rows]
    pairs = []

    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            e1, words1 = entries[i]
            e2, words2 = entries[j]
            intersection = words1 & words2
            union = words1 | words2
            similarity = len(intersection) / len(union) if union else 0

            if similarity >= threshold:
                pairs.append({
                    "entry_a": {"id": e1["id"], "name": e1["name"], "confidence": e1["confidence"]},
                    "entry_b": {"id": e2["id"], "name": e2["name"], "confidence": e2["confidence"]},
                    "similarity": round(similarity, 2),
                })

    return pairs


def merge_entries(conn: sqlite3.Connection, keep_id: int, remove_id: int) -> dict:
    """Merge two playbook entries: combine evidence, keep higher confidence.

    Returns the merged entry dict.
    """
    keep = conn.execute(
        "SELECT * FROM playbook_entries WHERE id = ?", (keep_id,)
    ).fetchone()
    remove = conn.execute(
        "SELECT * FROM playbook_entries WHERE id = ?", (remove_id,)
    ).fetchone()

    if not keep or not remove:
        return {"error": "One or both entries not found"}

    # Combine evidence lists
    try:
        keep_evidence = json.loads(keep["evidence"]) if keep["evidence"] else []
    except (json.JSONDecodeError, TypeError):
        keep_evidence = []
    try:
        remove_evidence = json.loads(remove["evidence"]) if remove["evidence"] else []
    except (json.JSONDecodeError, TypeError):
        remove_evidence = []

    merged_evidence = sorted(set(keep_evidence + remove_evidence))

    # Take higher confidence
    new_confidence = max(keep["confidence"], remove["confidence"])

    conn.execute(
        "UPDATE playbook_entries SET confidence = ?, evidence = ?, updated_at = datetime('now') "
        "WHERE id = ?",
        (new_confidence, json.dumps(merged_evidence), keep_id),
    )
    conn.execute("DELETE FROM playbook_entries WHERE id = ?", (remove_id,))
    conn.commit()

    logger.info(
        "Merged playbook entries: kept %s (id=%d), removed %s (id=%d)",
        keep["name"], keep_id, remove["name"], remove_id,
    )

    return {
        "kept": keep["name"],
        "removed": remove["name"],
        "new_confidence": new_confidence,
        "merged_evidence": merged_evidence,
    }


def make_dedup_tools(conn: sqlite3.Connection) -> list[ToolDef]:
    """Create dedup tool definitions for the GC agent."""
    return [
        ToolDef(
            name="find_similar_pairs",
            description="Find pairs of playbook entries with high name similarity (Jaccard > 0.8). "
                       "Review these to decide if they should be merged.",
            input_schema={
                "type": "object",
                "properties": {
                    "threshold": {"type": "number", "description": "Similarity threshold", "default": 0.8},
                },
                "required": [],
            },
            handler=lambda threshold=0.8: find_similar_pairs(conn, threshold),
        ),
        ToolDef(
            name="merge_entries",
            description="Merge two playbook entries. Keeps the entry with keep_id, "
                       "combines evidence from both, uses higher confidence, deletes the other.",
            input_schema={
                "type": "object",
                "properties": {
                    "keep_id": {"type": "integer", "description": "ID of the entry to keep"},
                    "remove_id": {"type": "integer", "description": "ID of the entry to remove"},
                },
                "required": ["keep_id", "remove_id"],
            },
            handler=lambda keep_id, remove_id: merge_entries(conn, keep_id, remove_id),
        ),
    ]
