"""Playbook trend query tools for the distill agent."""

from sqlalchemy.orm import Session

from engine.llm.types import ToolDef
from engine.agents import repository as repo


def make_trend_tools(session: Session) -> list[ToolDef]:
    """Create trend tool definitions bound to a DB session."""
    return [
        ToolDef(
            name="get_playbook_history",
            description="Get the confidence/maturity change history for a playbook entry by name.",
            input_schema={
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Playbook entry name (kebab-case)"}},
                "required": ["name"],
            },
            handler=lambda name: repo.get_playbook_history(session, name),
        ),
        ToolDef(
            name="get_stale_entries",
            description="Find playbook entries that haven't received new evidence in N days.",
            input_schema={
                "type": "object",
                "properties": {"days": {"type": "integer", "default": 14}},
                "required": [],
            },
            handler=lambda days=14: repo.get_stale_entries(session, days),
        ),
        ToolDef(
            name="get_similar_entries",
            description="Find playbook entries with similar names to detect potential duplicates.",
            input_schema={
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
            handler=lambda name: repo.get_similar_entries(session, name),
        ),
    ]
