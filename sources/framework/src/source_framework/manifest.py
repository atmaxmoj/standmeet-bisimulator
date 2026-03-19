"""Manifest dataclass + JSON loader for source plugins."""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class EventDef:
    """Event type definition from manifest."""

    label: str = ""
    color: str = ""


@dataclass
class DbDef:
    """Database table definition from manifest."""

    table: str = ""
    columns: dict[str, str] = field(default_factory=dict)
    indexes: list[str] = field(default_factory=list)


@dataclass
class UiDef:
    """UI rendering hints from manifest."""

    icon: str = ""
    visible_columns: list[str] = field(default_factory=list)
    searchable_columns: list[str] = field(default_factory=list)
    detail_columns: list[str] = field(default_factory=list)


@dataclass
class ContextDef:
    """Context formatting for LLM prompts."""

    description: str = ""
    format: str = ""


@dataclass
class GcDef:
    """Garbage collection configuration."""

    prompt: str = ""
    retention_days_default: int = 14


@dataclass
class ConfigField:
    """A single config field definition."""

    type: str = "string"
    default: str | int | float | bool = ""
    label: str = ""


@dataclass
class Manifest:
    """Complete source plugin manifest."""

    name: str
    version: str = "0.1.0"
    display_name: str = ""
    description: str = ""
    author: str = "builtin"
    platform: list[str] = field(default_factory=lambda: ["darwin", "win32"])
    entrypoint: str = ""

    events: dict[str, EventDef] = field(default_factory=dict)
    db: DbDef = field(default_factory=DbDef)
    ui: UiDef = field(default_factory=UiDef)
    context: ContextDef = field(default_factory=ContextDef)
    gc: GcDef = field(default_factory=GcDef)
    config: dict[str, ConfigField] = field(default_factory=dict)

    # Set by loader — not in JSON
    source_dir: Path = field(default_factory=lambda: Path("."))

    def supports_current_platform(self) -> bool:
        return sys.platform in self.platform

    def get_default_config(self) -> dict:
        return {k: v.default for k, v in self.config.items()}


def _parse_events(raw: dict) -> dict[str, EventDef]:
    return {
        k: EventDef(label=v.get("label", k), color=v.get("color", ""))
        for k, v in raw.items()
    }


def _parse_db(raw: dict) -> DbDef:
    return DbDef(
        table=raw.get("table", ""),
        columns=raw.get("columns", {}),
        indexes=raw.get("indexes", []),
    )


def _parse_ui(raw: dict) -> UiDef:
    return UiDef(
        icon=raw.get("icon", ""),
        visible_columns=raw.get("visible_columns", []),
        searchable_columns=raw.get("searchable_columns", []),
        detail_columns=raw.get("detail_columns", []),
    )


def _parse_context(raw: dict) -> ContextDef:
    return ContextDef(
        description=raw.get("description", ""),
        format=raw.get("format", ""),
    )


def _parse_gc(raw: dict) -> GcDef:
    return GcDef(
        prompt=raw.get("prompt", ""),
        retention_days_default=raw.get("retention_days_default", 14),
    )


def _parse_config(raw: dict) -> dict[str, ConfigField]:
    return {
        k: ConfigField(
            type=v.get("type", "string"),
            default=v.get("default", ""),
            label=v.get("label", k),
        )
        for k, v in raw.items()
    }


def load_manifest(path: Path) -> Manifest:
    """Load and validate a manifest.json file."""
    if path.is_dir():
        path = path / "manifest.json"

    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")

    with open(path) as f:
        raw = json.load(f)

    return parse_manifest(raw, source_dir=path.parent)


def parse_manifest(raw: dict, source_dir: Path | None = None) -> Manifest:
    """Parse a manifest dict into a Manifest dataclass."""
    if "name" not in raw:
        raise ValueError("Manifest missing required field: name")

    return Manifest(
        name=raw["name"],
        version=raw.get("version", "0.1.0"),
        display_name=raw.get("display_name", raw["name"]),
        description=raw.get("description", ""),
        author=raw.get("author", "builtin"),
        platform=raw.get("platform", ["darwin", "win32"]),
        entrypoint=raw.get("entrypoint", ""),
        events=_parse_events(raw.get("events", {})),
        db=_parse_db(raw.get("db", {})),
        ui=_parse_ui(raw.get("ui", {})),
        context=_parse_context(raw.get("context", {})),
        gc=_parse_gc(raw.get("gc", {})),
        config=_parse_config(raw.get("config", {})),
        source_dir=source_dir or Path("."),
    )
