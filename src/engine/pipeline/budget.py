"""Deterministic daily cost budget checking.

Layer 2 (architectural constraints): hard cap on daily LLM spend.
"""

import logging
import sqlite3

from engine.storage.sync_db import SyncDB

logger = logging.getLogger(__name__)


def check_daily_budget(conn: sqlite3.Connection, cap_usd: float) -> bool:
    """Return True if today's spend is under the cap, False otherwise.

    Reads actual cap from DB state table (UI-settable), falls back to cap_usd.
    """
    db = SyncDB(conn)
    actual_cap = db.get_budget_cap(cap_usd)
    spend = db.get_daily_spend()
    if spend >= actual_cap:
        logger.warning(
            "Daily budget exceeded: $%.4f >= $%.2f cap", spend, actual_cap,
        )
        return False
    return True
