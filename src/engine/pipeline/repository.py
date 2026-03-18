"""Pipeline data access — decay, budget. Uses SQLAlchemy ORM."""

from sqlalchemy import select, func

from engine.storage.session import get_session, ago
from engine.storage.models import PlaybookEntry, TokenUsage, State


def get_all_playbooks_for_decay(conn) -> list[dict]:
    s = get_session(conn)
    rows = s.execute(select(PlaybookEntry)).scalars().all()
    result = [
        {"id": r.id, "name": r.name, "confidence": r.confidence, "last_evidence_at": r.last_evidence_at}
        for r in rows
    ]
    s.close()
    return result


def update_confidence(conn, entry_id: int, confidence: float):
    s = get_session(conn)
    entry = s.get(PlaybookEntry, entry_id)
    if entry:
        entry.confidence = confidence
        s.commit()
    s.close()


def get_daily_spend(conn) -> float:
    s = get_session(conn)
    cutoff = ago(days=1)
    result = s.execute(
        select(func.coalesce(func.sum(TokenUsage.cost_usd), 0.0))
        .where(TokenUsage.created_at >= cutoff)
    ).scalar()
    s.close()
    return float(result)


def get_budget_cap(conn, default: float) -> float:
    s = get_session(conn)
    row = s.execute(
        select(State.value).where(State.key == "daily_cost_cap_usd")
    ).scalar_one_or_none()
    s.close()
    return float(row) if row else default
