"""Playbook trend query tools for the distill agent.

Layer 1 (context engineering): gives the Opus agent tools to inspect
playbook history, find stale entries, and detect similar entries.
The agent decides what to investigate based on the data it sees.
"""

import sqlite3

from engine.llm import ToolDef


def get_playbook_history(conn: sqlite3.Connection, name: str) -> list[dict]:
    """Get confidence/maturity change history for a playbook entry."""
    rows = conn.execute(
        "SELECT * FROM playbook_history WHERE playbook_name = ? ORDER BY created_at",
        (name,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_stale_entries(conn: sqlite3.Connection, days: int = 14) -> list[dict]:
    """Find playbook entries with no new evidence in N days."""
    rows = conn.execute(
        "SELECT id, name, confidence, maturity, evidence, last_evidence_at, updated_at "
        "FROM playbook_entries "
        "WHERE last_evidence_at IS NULL OR last_evidence_at < datetime('now', ?) "
        "ORDER BY confidence DESC",
        (f"-{days} days",),
    ).fetchall()
    return [dict(r) for r in rows]


def get_similar_entries(conn: sqlite3.Connection, name: str) -> list[dict]:
    """Find entries with similar names (word overlap heuristic).

    Uses Jaccard similarity on name words (split by hyphen).
    Returns entries with similarity > 0.3 (broad net — agent decides).
    """
    # Get the target entry's name words
    target_words = set(name.split("-"))
    if not target_words:
        return []

    rows = conn.execute(
        "SELECT id, name, confidence, maturity, context, evidence FROM playbook_entries "
        "WHERE name != ? ORDER BY confidence DESC",
        (name,),
    ).fetchall()

    results = []
    for r in rows:
        other_words = set(r["name"].split("-"))
        intersection = target_words & other_words
        union = target_words | other_words
        similarity = len(intersection) / len(union) if union else 0
        if similarity > 0.3:
            entry = dict(r)
            entry["similarity"] = round(similarity, 2)
            results.append(entry)

    return sorted(results, key=lambda x: x["similarity"], reverse=True)


def make_trend_tools(conn: sqlite3.Connection) -> list[ToolDef]:
    """Create trend tool definitions bound to a DB connection."""
    return [
        ToolDef(
            name="get_playbook_history",
            description="Get the confidence/maturity change history for a playbook entry by name.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Playbook entry name (kebab-case)"},
                },
                "required": ["name"],
            },
            handler=lambda name: get_playbook_history(conn, name),
        ),
        ToolDef(
            name="get_stale_entries",
            description="Find playbook entries that haven't received new evidence in N days. "
                       "These may be outdated or need re-validation.",
            input_schema={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Days threshold", "default": 14},
                },
                "required": [],
            },
            handler=lambda days=14: get_stale_entries(conn, days),
        ),
        ToolDef(
            name="get_similar_entries",
            description="Find playbook entries with similar names to detect potential duplicates or related patterns.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Playbook entry name to compare against"},
                },
                "required": ["name"],
            },
            handler=lambda name: get_similar_entries(conn, name),
        ),
    ]
