"""Memory Protocol REST endpoints + engine management."""

from fastapi import APIRouter, Request

router = APIRouter()


# -- Memory Protocol: episodes --


@router.get("/memory/episodes/")
async def list_episodes(request: Request, limit: int = 50, offset: int = 0):
    db = request.app.state.db
    episodes = await db.get_all_episodes(limit=limit, offset=offset)
    return {"episodes": episodes}


# -- Memory Protocol: playbooks --


@router.get("/memory/playbooks/")
async def list_playbooks(request: Request):
    db = request.app.state.db
    playbooks = await db.get_all_playbooks()
    return {"playbooks": playbooks}


# -- Engine management --


@router.get("/engine/status")
async def engine_status(request: Request):
    db = request.app.state.db
    status = await db.get_status()
    return status


@router.post("/engine/distill")
async def trigger_distill(request: Request):
    """Manually trigger weekly distillation (for testing)."""
    from engine.pipeline.distill import weekly_distill

    client = request.app.state.anthropic
    db = request.app.state.db
    count = await weekly_distill(client, db)
    return {"playbook_entries_updated": count}


# -- Test helper: manually ingest events --


@router.post("/test/ingest")
async def test_ingest(request: Request):
    """
    POST raw text as a test episode (bypasses Screenpipe + filter + Haiku).
    Body: {"summary": "...", "app_names": ["VSCode"], "started_at": "...", "ended_at": "..."}
    """
    body = await request.json()
    db = request.app.state.db
    episode_id = await db.insert_episode(
        summary=body["summary"],
        app_names=str(body.get("app_names", "[]")),
        frame_count=0,
        started_at=body.get("started_at", ""),
        ended_at=body.get("ended_at", ""),
    )
    return {"episode_id": episode_id}
