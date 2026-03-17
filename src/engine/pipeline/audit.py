"""Evidence audit tools + playbook snapshots + raw data GC for the GC agent.

Layer 3 (garbage collection): tools for the GC agent to check data
integrity, record history before making changes, and manage raw capture
data (frames, audio, os_events, pipeline_logs).
"""

import json
import logging
import os
import sqlite3

from engine.infra.llm import ToolDef

logger = logging.getLogger(__name__)


def check_evidence_exists(conn: sqlite3.Connection, entry_name: str) -> dict:
    """Check if evidence episode IDs for a playbook entry still exist in DB."""
    row = conn.execute(
        "SELECT id, name, evidence FROM playbook_entries WHERE name = ?",
        (entry_name,),
    ).fetchone()

    if not row:
        return {"error": f"Entry '{entry_name}' not found"}

    try:
        evidence_ids = json.loads(row["evidence"]) if row["evidence"] else []
    except (json.JSONDecodeError, TypeError):
        evidence_ids = []

    if not evidence_ids:
        return {"name": entry_name, "evidence_ids": [], "missing": [], "all_exist": True}

    placeholders = ",".join("?" * len(evidence_ids))
    existing = conn.execute(
        f"SELECT id FROM episodes WHERE id IN ({placeholders})",
        evidence_ids,
    ).fetchall()
    existing_ids = {r["id"] for r in existing}

    missing = [eid for eid in evidence_ids if eid not in existing_ids]

    return {
        "name": entry_name,
        "evidence_ids": evidence_ids,
        "missing": missing,
        "all_exist": len(missing) == 0,
    }


def check_maturity_consistency(conn: sqlite3.Connection) -> list[dict]:
    """Find entries where maturity level doesn't match evidence count.

    Rules:
    - mature/mastered should have >= 8 evidence episodes
    - developing should have >= 3
    """
    rows = conn.execute(
        "SELECT id, name, confidence, maturity, evidence FROM playbook_entries"
    ).fetchall()

    inconsistent = []
    for r in rows:
        try:
            evidence = json.loads(r["evidence"]) if r["evidence"] else []
        except (json.JSONDecodeError, TypeError):
            evidence = []

        count = len(evidence)
        maturity = r["maturity"] or "nascent"
        issue = None

        if maturity in ("mature", "mastered") and count < 8:
            issue = f"{maturity} with only {count} evidence episodes (expected >= 8)"
        elif maturity == "developing" and count < 3:
            issue = f"developing with only {count} evidence episodes (expected >= 3)"

        if issue:
            inconsistent.append({
                "id": r["id"],
                "name": r["name"],
                "maturity": maturity,
                "evidence_count": count,
                "confidence": r["confidence"],
                "issue": issue,
            })

    return inconsistent


def record_snapshot(conn: sqlite3.Connection, name: str, reason: str = "") -> dict:
    """Record current state of a playbook entry into history before modification."""
    row = conn.execute(
        "SELECT * FROM playbook_entries WHERE name = ?", (name,),
    ).fetchone()

    if not row:
        return {"error": f"Entry '{name}' not found"}

    conn.execute(
        "INSERT INTO playbook_history (playbook_name, confidence, maturity, evidence, change_reason) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, row["confidence"], row["maturity"] or "nascent", row["evidence"] or "[]", reason),
    )
    conn.commit()

    return {
        "name": name,
        "snapshot_confidence": row["confidence"],
        "snapshot_maturity": row["maturity"],
        "reason": reason,
    }


def deprecate_entry(conn: sqlite3.Connection, entry_id: int, reason: str = "") -> dict:
    """Set a playbook entry's confidence to 0 and maturity to 'nascent' (soft deprecate)."""
    row = conn.execute(
        "SELECT name, confidence, maturity, evidence FROM playbook_entries WHERE id = ?",
        (entry_id,),
    ).fetchone()

    if not row:
        return {"error": f"Entry id={entry_id} not found"}

    # Snapshot before deprecating
    record_snapshot(conn, row["name"], reason=f"deprecated: {reason}")

    conn.execute(
        "UPDATE playbook_entries SET confidence = 0.0, maturity = 'nascent', "
        "updated_at = datetime('now') WHERE id = ?",
        (entry_id,),
    )
    conn.commit()

    logger.info("Deprecated playbook entry %s (id=%d): %s", row["name"], entry_id, reason)

    return {"name": row["name"], "deprecated": True, "reason": reason}


# -- Raw data inspection + purge tools --


def get_data_stats(conn: sqlite3.Connection) -> dict:
    """Get row counts for all raw data tables (total, processed, unprocessed)."""
    stats = {}
    for table, has_processed in [
        ("frames", True), ("audio_frames", True),
        ("os_events", True), ("pipeline_logs", False),
    ]:
        total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if has_processed:
            processed = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE processed = 1"
            ).fetchone()[0]
            stats[table] = {
                "total": total,
                "processed": processed,
                "unprocessed": total - processed,
            }
        else:
            stats[table] = {"total": total}
    return stats


def get_oldest_processed(conn: sqlite3.Connection) -> dict:
    """Get the created_at of the oldest processed row in each table."""
    result = {}
    for table in ("frames", "audio_frames", "os_events"):
        row = conn.execute(
            f"SELECT MIN(created_at) as oldest FROM {table} WHERE processed = 1"
        ).fetchone()
        result[table] = row["oldest"] if row and row["oldest"] else None

    row = conn.execute(
        "SELECT MIN(created_at) as oldest FROM pipeline_logs"
    ).fetchone()
    result["pipeline_logs"] = row["oldest"] if row and row["oldest"] else None
    return result


def purge_processed_frames(conn: sqlite3.Connection, older_than_days: int) -> dict:
    """Delete processed frames older than N days + their image files on disk."""
    rows = conn.execute(
        "SELECT id, image_path FROM frames "
        "WHERE processed = 1 AND created_at < datetime('now', ?)",
        (f"-{older_than_days} days",),
    ).fetchall()

    if not rows:
        return {"deleted": 0, "files_deleted": 0}

    files_deleted = 0
    for r in rows:
        if r["image_path"]:
            try:
                os.remove(r["image_path"])
                files_deleted += 1
            except OSError:
                pass

    ids = [r["id"] for r in rows]
    placeholders = ",".join("?" * len(ids))
    conn.execute(f"DELETE FROM frames WHERE id IN ({placeholders})", ids)
    conn.commit()

    logger.info("Purged %d processed frames (%d files)", len(ids), files_deleted)
    return {"deleted": len(ids), "files_deleted": files_deleted}


def purge_processed_audio(conn: sqlite3.Connection, older_than_days: int) -> dict:
    """Delete processed audio frames older than N days + their chunk files on disk."""
    rows = conn.execute(
        "SELECT id, chunk_path FROM audio_frames "
        "WHERE processed = 1 AND created_at < datetime('now', ?)",
        (f"-{older_than_days} days",),
    ).fetchall()

    if not rows:
        return {"deleted": 0, "files_deleted": 0}

    files_deleted = 0
    for r in rows:
        if r["chunk_path"]:
            try:
                os.remove(r["chunk_path"])
                files_deleted += 1
            except OSError:
                pass

    ids = [r["id"] for r in rows]
    placeholders = ",".join("?" * len(ids))
    conn.execute(f"DELETE FROM audio_frames WHERE id IN ({placeholders})", ids)
    conn.commit()

    logger.info("Purged %d processed audio frames (%d files)", len(ids), files_deleted)
    return {"deleted": len(ids), "files_deleted": files_deleted}


def purge_processed_os_events(conn: sqlite3.Connection, older_than_days: int) -> dict:
    """Delete processed os_events older than N days."""
    cur = conn.execute(
        "DELETE FROM os_events WHERE processed = 1 AND created_at < datetime('now', ?)",
        (f"-{older_than_days} days",),
    )
    conn.commit()
    deleted = cur.rowcount
    if deleted:
        logger.info("Purged %d processed os_events", deleted)
    return {"deleted": deleted}


def purge_pipeline_logs(conn: sqlite3.Connection, older_than_days: int) -> dict:
    """Delete pipeline_logs older than N days."""
    cur = conn.execute(
        "DELETE FROM pipeline_logs WHERE created_at < datetime('now', ?)",
        (f"-{older_than_days} days",),
    )
    conn.commit()
    deleted = cur.rowcount
    if deleted:
        logger.info("Purged %d pipeline logs", deleted)
    return {"deleted": deleted}


def make_audit_tools(conn: sqlite3.Connection) -> list[ToolDef]:
    """Create audit tool definitions for the GC agent."""
    return [
        ToolDef(
            name="check_evidence_exists",
            description="Check if evidence episode IDs for a playbook entry still exist in the database.",
            input_schema={
                "type": "object",
                "properties": {
                    "entry_name": {"type": "string", "description": "Playbook entry name"},
                },
                "required": ["entry_name"],
            },
            handler=lambda entry_name: check_evidence_exists(conn, entry_name),
        ),
        ToolDef(
            name="check_maturity_consistency",
            description="Find entries where maturity level doesn't match evidence count "
                       "(e.g., 'mature' with only 2 evidence episodes).",
            input_schema={
                "type": "object",
                "properties": {},
                "required": [],
            },
            handler=lambda: check_maturity_consistency(conn),
        ),
        ToolDef(
            name="record_snapshot",
            description="Record current state of a playbook entry into history before making changes.",
            input_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "Playbook entry name"},
                    "reason": {"type": "string", "description": "Reason for the snapshot"},
                },
                "required": ["name"],
            },
            handler=lambda name, reason="": record_snapshot(conn, name, reason),
        ),
        ToolDef(
            name="deprecate_entry",
            description="Soft-deprecate a playbook entry (set confidence=0, maturity=nascent). "
                       "Use when an entry is no longer valid or has been superseded.",
            input_schema={
                "type": "object",
                "properties": {
                    "entry_id": {"type": "integer", "description": "ID of entry to deprecate"},
                    "reason": {"type": "string", "description": "Why this entry is being deprecated"},
                },
                "required": ["entry_id"],
            },
            handler=lambda entry_id, reason="": deprecate_entry(conn, entry_id, reason),
        ),
        # -- Raw data GC tools --
        ToolDef(
            name="get_data_stats",
            description="Get row counts for all raw data tables: frames, audio_frames, os_events, pipeline_logs. "
                       "Shows total, processed, and unprocessed counts. Use this to understand data volume before deciding what to purge.",
            input_schema={
                "type": "object",
                "properties": {},
                "required": [],
            },
            handler=lambda: get_data_stats(conn),
        ),
        ToolDef(
            name="get_oldest_processed",
            description="Get the timestamp of the oldest processed record in each raw data table. "
                       "Helps you understand how far back the data goes.",
            input_schema={
                "type": "object",
                "properties": {},
                "required": [],
            },
            handler=lambda: get_oldest_processed(conn),
        ),
        ToolDef(
            name="purge_processed_frames",
            description="Delete processed screen capture frames older than N days, including their image files on disk. "
                       "Only deletes frames that have already been processed into episodes. "
                       "Choose the retention period based on data volume and how old the data is.",
            input_schema={
                "type": "object",
                "properties": {
                    "older_than_days": {
                        "type": "integer",
                        "description": "Delete frames older than this many days",
                    },
                },
                "required": ["older_than_days"],
            },
            handler=lambda older_than_days: purge_processed_frames(conn, older_than_days),
        ),
        ToolDef(
            name="purge_processed_audio",
            description="Delete processed audio transcription frames older than N days, including chunk files on disk. "
                       "Only deletes audio that has already been processed into episodes.",
            input_schema={
                "type": "object",
                "properties": {
                    "older_than_days": {
                        "type": "integer",
                        "description": "Delete audio frames older than this many days",
                    },
                },
                "required": ["older_than_days"],
            },
            handler=lambda older_than_days: purge_processed_audio(conn, older_than_days),
        ),
        ToolDef(
            name="purge_processed_os_events",
            description="Delete processed OS events (shell commands, browser URLs) older than N days. "
                       "Only deletes events that have already been processed into episodes.",
            input_schema={
                "type": "object",
                "properties": {
                    "older_than_days": {
                        "type": "integer",
                        "description": "Delete os_events older than this many days",
                    },
                },
                "required": ["older_than_days"],
            },
            handler=lambda older_than_days: purge_processed_os_events(conn, older_than_days),
        ),
        ToolDef(
            name="purge_pipeline_logs",
            description="Delete pipeline logs (LLM prompts/responses) older than N days. "
                       "These are debug logs and can be large. Choose retention based on volume.",
            input_schema={
                "type": "object",
                "properties": {
                    "older_than_days": {
                        "type": "integer",
                        "description": "Delete logs older than this many days",
                    },
                },
                "required": ["older_than_days"],
            },
            handler=lambda older_than_days: purge_pipeline_logs(conn, older_than_days),
        ),
    ]
