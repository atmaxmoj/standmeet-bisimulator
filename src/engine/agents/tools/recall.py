"""Recall tools for the episode/distill agents.

Layer 1 (context engineering): gives agents tools to search episode history
and raw capture data.
"""

from sqlalchemy.orm import Session

from engine.llm.types import ToolDef
from engine.agents import repository as repo


def make_recall_tools(session: Session) -> list[ToolDef]:
    """Create recall tool definitions bound to a DB session."""
    return [
        ToolDef(
            name="search_episodes",
            description="Search historical episode summaries by keyword.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword"},
                    "limit": {"type": "integer", "description": "Max results", "default": 10},
                },
                "required": ["query"],
            },
            handler=lambda query, limit=10: repo.search_episodes(session, query, limit),
        ),
        ToolDef(
            name="get_recent_episodes",
            description="Get episodes from the last N hours.",
            input_schema={
                "type": "object",
                "properties": {
                    "hours": {"type": "integer", "description": "Hours to look back", "default": 24},
                },
                "required": [],
            },
            handler=lambda hours=24: repo.get_recent_episodes(session, hours),
        ),
        ToolDef(
            name="get_episodes_by_app",
            description="Get episodes involving a specific application.",
            input_schema={
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Application name"},
                },
                "required": ["app_name"],
            },
            handler=lambda app_name: repo.get_episodes_by_app(session, app_name),
        ),
        ToolDef(
            name="get_recent_frames",
            description="Get recent screen capture frames (OCR text, app name, window name).",
            input_schema={
                "type": "object",
                "properties": {
                    "hours": {"type": "integer", "default": 24},
                    "limit": {"type": "integer", "default": 50},
                },
                "required": [],
            },
            handler=lambda hours=24, limit=50: repo.get_recent_frames(session, hours, limit),
        ),
        ToolDef(
            name="get_frames_by_app",
            description="Get screen capture frames from a specific application.",
            input_schema={
                "type": "object",
                "properties": {
                    "app_name": {"type": "string"},
                    "limit": {"type": "integer", "default": 30},
                },
                "required": ["app_name"],
            },
            handler=lambda app_name, limit=30: repo.get_frames_by_app(session, app_name, limit),
        ),
        ToolDef(
            name="get_recent_audio",
            description="Get recent audio transcriptions.",
            input_schema={
                "type": "object",
                "properties": {
                    "hours": {"type": "integer", "default": 24},
                    "limit": {"type": "integer", "default": 50},
                },
                "required": [],
            },
            handler=lambda hours=24, limit=50: repo.get_recent_audio(session, hours, limit),
        ),
        ToolDef(
            name="get_recent_os_events",
            description="Get recent OS events (shell commands, browser URLs).",
            input_schema={
                "type": "object",
                "properties": {
                    "hours": {"type": "integer", "default": 24},
                    "limit": {"type": "integer", "default": 50},
                },
                "required": [],
            },
            handler=lambda hours=24, limit=50: repo.get_recent_os_events(session, hours, limit),
        ),
        ToolDef(
            name="get_os_events_by_type",
            description="Get OS events filtered by type ('shell', 'url').",
            input_schema={
                "type": "object",
                "properties": {
                    "event_type": {"type": "string"},
                    "limit": {"type": "integer", "default": 30},
                },
                "required": ["event_type"],
            },
            handler=lambda event_type, limit=30: repo.get_os_events_by_type(session, event_type, limit),
        ),
    ]
