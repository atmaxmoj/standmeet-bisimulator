"""Deterministic daily cost budget checking.

Layer 2 (architectural constraints): hard cap on daily LLM spend.
"""

import logging
import sqlite3

logger = logging.getLogger(__name__)


def get_daily_spend(conn: sqlite3.Connection) -> float:
    """Sum today's LLM costs from token_usage table."""
    row = conn.execute(
        "SELECT COALESCE(SUM(cost_usd), 0.0) as total "
        "FROM token_usage "
        "WHERE created_at >= datetime('now', '-1 days')",
    ).fetchone()
    return float(row["total"] if isinstance(row, sqlite3.Row) else row[0])


def check_daily_budget(conn: sqlite3.Connection, cap_usd: float) -> bool:
    """Return True if today's spend is under the cap, False otherwise."""
    spend = get_daily_spend(conn)
    if spend >= cap_usd:
        logger.warning(
            "Daily budget exceeded: $%.4f >= $%.2f cap", spend, cap_usd,
        )
        return False
    return True
