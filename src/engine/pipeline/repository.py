"""Pipeline data access — decay, budget."""

import logging
import sqlite3

logger = logging.getLogger(__name__)

DECAY_DAYS = 90
DECAY_FLOOR = 0.3


def get_all_playbooks_for_decay(conn: sqlite3.Connection) -> list[dict]:
    """Get playbook entries with fields needed for confidence decay."""
    rows = conn.execute(
        "SELECT id, name, confidence, last_evidence_at FROM playbook_entries"
    ).fetchall()
    return [dict(r) for r in rows]


def update_confidence(conn: sqlite3.Connection, entry_id: int, confidence: float):
    conn.execute(
        "UPDATE playbook_entries SET confidence = ? WHERE id = ?",
        (confidence, entry_id),
    )


def get_daily_spend(conn: sqlite3.Connection) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0.0) as total "
        "FROM token_usage WHERE created_at >= datetime('now', '-1 days')",
    ).fetchone()
    return float(row["total"] if isinstance(row, sqlite3.Row) else row[0])


def get_budget_cap(conn: sqlite3.Connection, default: float) -> float:
    row = conn.execute(
        "SELECT value FROM state WHERE key = 'daily_cost_cap_usd'",
    ).fetchone()
    if row:
        return float(row["value"] if isinstance(row, sqlite3.Row) else row[0])
    return default
