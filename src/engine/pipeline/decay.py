"""Deterministic confidence time decay for playbook entries.

Layer 3 (garbage collection): entries that haven't received new evidence
decay toward a floor. This is purely mathematical — no LLM involved.

Formula: effective = confidence * max(0.3, 1.0 - days_since_evidence / 90)
- Floor at 30% of original confidence (never decays to zero)
- Full decay over 90 days without evidence
- Entries with recent evidence are unaffected
"""

import logging
import sqlite3
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DECAY_DAYS = 90
DECAY_FLOOR = 0.3


def decay_confidence(conn: sqlite3.Connection) -> int:
    """Apply time-based confidence decay to all playbook entries.

    Returns number of entries updated.
    """
    rows = conn.execute(
        "SELECT id, name, confidence, last_evidence_at FROM playbook_entries"
    ).fetchall()

    updated = 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for r in rows:
        last_evidence = r["last_evidence_at"]
        if not last_evidence:
            # No evidence date — use created_at or assume very old
            days_since = DECAY_DAYS  # max decay
        else:
            try:
                last_dt = datetime.fromisoformat(last_evidence.replace("Z", "+00:00")).replace(tzinfo=None)
                days_since = (now - last_dt).total_seconds() / 86400
            except (ValueError, AttributeError):
                days_since = DECAY_DAYS

        if days_since <= 0:
            continue

        decay_factor = max(DECAY_FLOOR, 1.0 - days_since / DECAY_DAYS)
        original = r["confidence"]
        new_confidence = round(original * decay_factor, 4)

        if abs(new_confidence - original) < 0.0001:
            continue

        conn.execute(
            "UPDATE playbook_entries SET confidence = ? WHERE id = ?",
            (new_confidence, r["id"]),
        )
        updated += 1
        logger.debug(
            "Decayed %s: %.4f → %.4f (%.0f days since evidence)",
            r["name"], original, new_confidence, days_since,
        )

    if updated:
        conn.commit()
        logger.info("Decayed confidence for %d entries", updated)

    return updated
