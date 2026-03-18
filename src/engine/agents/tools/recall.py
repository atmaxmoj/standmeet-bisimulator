"""Recall tools for the episode/distill agents.

Layer 1 (context engineering): gives agents tools to search episode history
and raw capture data. The agent decides what to look up based on context.
"""

import sqlite3

from engine.llm.types import ToolDef


def search_episodes(conn: sqlite3.Connection, query: str, limit: int = 10) -> list[dict]:
    """Search episode summaries by keyword (SQLite LIKE)."""
    rows = conn.execute(
        "SELECT id, summary, app_names, started_at, ended_at "
        "FROM episodes WHERE summary LIKE ? ORDER BY id DESC LIMIT ?",
        (f"%{query}%", limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_recent_episodes(conn: sqlite3.Connection, hours: int = 24) -> list[dict]:
    """Get episodes from the last N hours."""
    rows = conn.execute(
        "SELECT id, summary, app_names, started_at, ended_at "
        "FROM episodes WHERE created_at >= datetime('now', ?) ORDER BY created_at DESC",
        (f"-{hours} hours",),
    ).fetchall()
    return [dict(r) for r in rows]


def get_episodes_by_app(conn: sqlite3.Connection, app_name: str) -> list[dict]:
    """Get episodes that involve a specific app."""
    rows = conn.execute(
        "SELECT id, summary, app_names, started_at, ended_at "
        "FROM episodes WHERE app_names LIKE ? ORDER BY id DESC LIMIT 20",
        (f"%{app_name}%",),
    ).fetchall()
    return [dict(r) for r in rows]


# -- Raw capture data access --


def get_recent_frames(conn: sqlite3.Connection, hours: int = 24, limit: int = 50) -> list[dict]:
    """Get recent screen capture frames. Text truncated to 300 chars."""
    rows = conn.execute(
        "SELECT id, timestamp, app_name, window_name, "
        "substr(text, 1, 300) as text, display_id "
        "FROM frames WHERE created_at >= datetime('now', ?) "
        "ORDER BY id DESC LIMIT ?",
        (f"-{hours} hours", limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_frames_by_app(conn: sqlite3.Connection, app_name: str, limit: int = 30) -> list[dict]:
    """Get frames from a specific app. Text truncated to 300 chars."""
    rows = conn.execute(
        "SELECT id, timestamp, app_name, window_name, "
        "substr(text, 1, 300) as text, display_id "
        "FROM frames WHERE app_name LIKE ? ORDER BY id DESC LIMIT ?",
        (f"%{app_name}%", limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_recent_audio(conn: sqlite3.Connection, hours: int = 24, limit: int = 50) -> list[dict]:
    """Get recent audio transcriptions."""
    rows = conn.execute(
        "SELECT id, timestamp, text, language, duration_seconds, source "
        "FROM audio_frames WHERE created_at >= datetime('now', ?) "
        "ORDER BY id DESC LIMIT ?",
        (f"-{hours} hours", limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_recent_os_events(conn: sqlite3.Connection, hours: int = 24, limit: int = 50) -> list[dict]:
    """Get recent OS events (shell commands, browser URLs)."""
    rows = conn.execute(
        "SELECT id, timestamp, event_type, source, data "
        "FROM os_events WHERE created_at >= datetime('now', ?) "
        "ORDER BY id DESC LIMIT ?",
        (f"-{hours} hours", limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_os_events_by_type(conn: sqlite3.Connection, event_type: str, limit: int = 30) -> list[dict]:
    """Get OS events filtered by type (e.g., 'shell', 'url')."""
    rows = conn.execute(
        "SELECT id, timestamp, event_type, source, data "
        "FROM os_events WHERE event_type = ? ORDER BY id DESC LIMIT ?",
        (event_type, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def make_recall_tools(conn: sqlite3.Connection) -> list[ToolDef]:
    """Create recall tool definitions bound to a DB connection."""
    return [
        ToolDef(
            name="search_episodes",
            description="Search historical episode summaries by keyword. Use this to find patterns in past behavior.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search keyword"},
                    "limit": {"type": "integer", "description": "Max results", "default": 10},
                },
                "required": ["query"],
            },
            handler=lambda query, limit=10: search_episodes(conn, query, limit),
        ),
        ToolDef(
            name="get_recent_episodes",
            description="Get episodes from the last N hours. Useful for understanding recent context.",
            input_schema={
                "type": "object",
                "properties": {
                    "hours": {"type": "integer", "description": "Hours to look back", "default": 24},
                },
                "required": [],
            },
            handler=lambda hours=24: get_recent_episodes(conn, hours),
        ),
        ToolDef(
            name="get_episodes_by_app",
            description="Get episodes involving a specific application (e.g., 'VSCode', 'Chrome').",
            input_schema={
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Application name to filter by"},
                },
                "required": ["app_name"],
            },
            handler=lambda app_name: get_episodes_by_app(conn, app_name),
        ),
        # -- Raw capture data tools --
        ToolDef(
            name="get_recent_frames",
            description="Get recent screen capture frames (OCR text, app name, window name). "
                       "Use this to see what the user was looking at on screen.",
            input_schema={
                "type": "object",
                "properties": {
                    "hours": {"type": "integer", "description": "Hours to look back", "default": 24},
                    "limit": {"type": "integer", "description": "Max results", "default": 50},
                },
                "required": [],
            },
            handler=lambda hours=24, limit=50: get_recent_frames(conn, hours, limit),
        ),
        ToolDef(
            name="get_frames_by_app",
            description="Get screen capture frames from a specific application (e.g., 'VSCode', 'Chrome', 'Terminal').",
            input_schema={
                "type": "object",
                "properties": {
                    "app_name": {"type": "string", "description": "Application name to filter by"},
                    "limit": {"type": "integer", "description": "Max results", "default": 30},
                },
                "required": ["app_name"],
            },
            handler=lambda app_name, limit=30: get_frames_by_app(conn, app_name, limit),
        ),
        ToolDef(
            name="get_recent_audio",
            description="Get recent audio transcriptions (speech-to-text from microphone). "
                       "Use this to understand what the user was saying or hearing.",
            input_schema={
                "type": "object",
                "properties": {
                    "hours": {"type": "integer", "description": "Hours to look back", "default": 24},
                    "limit": {"type": "integer", "description": "Max results", "default": 50},
                },
                "required": [],
            },
            handler=lambda hours=24, limit=50: get_recent_audio(conn, hours, limit),
        ),
        ToolDef(
            name="get_recent_os_events",
            description="Get recent OS events including shell commands and browser URLs. "
                       "Use this to understand what commands were run or sites visited.",
            input_schema={
                "type": "object",
                "properties": {
                    "hours": {"type": "integer", "description": "Hours to look back", "default": 24},
                    "limit": {"type": "integer", "description": "Max results", "default": 50},
                },
                "required": [],
            },
            handler=lambda hours=24, limit=50: get_recent_os_events(conn, hours, limit),
        ),
        ToolDef(
            name="get_os_events_by_type",
            description="Get OS events filtered by type. Common types: 'shell' (terminal commands), 'url' (browser navigation).",
            input_schema={
                "type": "object",
                "properties": {
                    "event_type": {"type": "string", "description": "Event type to filter (e.g., 'shell', 'url')"},
                    "limit": {"type": "integer", "description": "Max results", "default": 30},
                },
                "required": ["event_type"],
            },
            handler=lambda event_type, limit=30: get_os_events_by_type(conn, event_type, limit),
        ),
    ]
