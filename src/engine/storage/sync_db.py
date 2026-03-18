"""Synchronous DB wrapper for pipeline/scheduler/tools.

Mirrors the async DB class methods but uses sync sqlite3.Connection.
Centralizes all SQL so callers don't write raw queries.
"""

import sqlite3


class SyncDB:
    """Thin sync wrapper around a sqlite3.Connection."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ── Token usage ──

    def record_usage(
        self, model: str, layer: str,
        input_tokens: int, output_tokens: int, cost_usd: float,
    ):
        self.conn.execute(
            "INSERT INTO token_usage (model, layer, input_tokens, output_tokens, cost_usd) "
            "VALUES (?, ?, ?, ?, ?)",
            (model, layer, input_tokens, output_tokens, cost_usd),
        )

    # ── Pipeline logs ──

    def insert_pipeline_log(
        self, stage: str, prompt: str, response: str,
        model: str = "", input_tokens: int = 0,
        output_tokens: int = 0, cost_usd: float = 0.0,
    ):
        self.conn.execute(
            "INSERT INTO pipeline_logs (stage, prompt, response, model, input_tokens, output_tokens, cost_usd) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (stage, prompt, response, model, input_tokens, output_tokens, cost_usd),
        )

    # ── Episodes ──

    def get_recent_episodes(self, days: int = 1) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM episodes WHERE created_at >= datetime('now', ?) ORDER BY created_at",
            (f"-{days} days",),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Playbook entries ──

    def get_all_playbooks(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM playbook_entries ORDER BY confidence DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def upsert_playbook(
        self, name: str, context: str, action: str,
        confidence: float, maturity: str, evidence: str,
    ):
        self.conn.execute(
            "INSERT INTO playbook_entries (name, context, action, confidence, maturity, evidence, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, datetime('now')) "
            "ON CONFLICT(name) DO UPDATE SET "
            "context=excluded.context, action=excluded.action, "
            "confidence=excluded.confidence, maturity=excluded.maturity, "
            "evidence=excluded.evidence, updated_at=datetime('now')",
            (name, context, action, confidence, maturity, evidence),
        )

    def count_recent_playbooks(self, hours: int = 1) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM playbook_entries WHERE updated_at >= datetime('now', ?)",
            (f"-{hours} hours",),
        ).fetchone()[0]

    # ── Routines ──

    def get_all_routines(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM routines ORDER BY confidence DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def upsert_routine(
        self, name: str, trigger: str, goal: str,
        steps: str, uses: str, confidence: float, maturity: str,
    ):
        self.conn.execute(
            "INSERT INTO routines (name, trigger, goal, steps, uses, confidence, maturity, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now')) "
            "ON CONFLICT(name) DO UPDATE SET "
            "trigger=excluded.trigger, goal=excluded.goal, steps=excluded.steps, "
            "uses=excluded.uses, confidence=excluded.confidence, maturity=excluded.maturity, "
            "updated_at=datetime('now')",
            (name, trigger, goal, steps, uses, confidence, maturity),
        )

    def count_recent_routines(self, hours: int = 1) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM routines WHERE updated_at >= datetime('now', ?)",
            (f"-{hours} hours",),
        ).fetchone()[0]

    # ── Processed marking ──

    def mark_processed(
        self,
        screen_ids: set[int],
        audio_ids: set[int],
        os_event_ids: set[int] | None = None,
    ):
        if screen_ids:
            ph = ",".join("?" * len(screen_ids))
            self.conn.execute(f"UPDATE frames SET processed = 1 WHERE id IN ({ph})", list(screen_ids))
        if audio_ids:
            ph = ",".join("?" * len(audio_ids))
            self.conn.execute(f"UPDATE audio_frames SET processed = 1 WHERE id IN ({ph})", list(audio_ids))
        if os_event_ids:
            ph = ",".join("?" * len(os_event_ids))
            self.conn.execute(f"UPDATE os_events SET processed = 1 WHERE id IN ({ph})", list(os_event_ids))
        self.conn.commit()

    # ── Budget ──

    def get_daily_spend(self) -> float:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0.0) as total "
            "FROM token_usage WHERE created_at >= datetime('now', '-1 days')",
        ).fetchone()
        return float(row["total"] if isinstance(row, sqlite3.Row) else row[0])

    def get_budget_cap(self, default: float) -> float:
        row = self.conn.execute(
            "SELECT value FROM state WHERE key = 'daily_cost_cap_usd'",
        ).fetchone()
        if row:
            return float(row["value"] if isinstance(row, sqlite3.Row) else row[0])
        return default
