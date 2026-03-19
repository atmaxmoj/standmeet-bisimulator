"""Tests for manifest loading and parsing."""

import json
import tempfile
from pathlib import Path

import pytest

from source_framework.manifest import Manifest, load_manifest, parse_manifest


MINIMAL_MANIFEST = {"name": "test_source"}

FULL_MANIFEST = {
    "name": "screen",
    "version": "0.1.0",
    "display_name": "Screen Capture",
    "description": "Screenshot + OCR of all displays",
    "author": "builtin",
    "platform": ["darwin", "win32"],
    "entrypoint": "screen_source:ScreenSource",
    "events": {
        "screen_frame": {
            "label": "Screen Frame",
            "color": "blue",
        }
    },
    "db": {
        "table": "screen_data",
        "columns": {
            "timestamp": "timestamptz not null",
            "app_name": "text not null default ''",
            "window_name": "text not null default ''",
            "text": "text not null default ''",
            "display_id": "integer not null default 0",
            "image_hash": "text not null default ''",
            "image_path": "text not null default ''",
            "processed": "integer not null default 0",
        },
        "indexes": ["processed", "timestamp"],
    },
    "ui": {
        "icon": "monitor",
        "visible_columns": ["timestamp", "app_name", "window_name", "text"],
        "searchable_columns": ["app_name", "window_name", "text"],
        "detail_columns": ["image_path"],
    },
    "context": {
        "description": "Screenshots with OCR text",
        "format": "[{timestamp}] {app_name}/{window_name}: {text}",
    },
    "gc": {
        "prompt": "Screen frames older than {retention_days} days...",
        "retention_days_default": 14,
    },
    "config": {
        "interval_seconds": {"type": "number", "default": 3, "label": "Capture interval"},
        "max_width": {"type": "number", "default": 1024, "label": "Max image width"},
        "webp_quality": {"type": "number", "default": 80, "label": "WebP quality (0-100)"},
    },
}


class TestParseManifest:
    def test_minimal(self):
        m = parse_manifest(MINIMAL_MANIFEST)
        assert m.name == "test_source"
        assert m.version == "0.1.0"
        assert m.display_name == "test_source"
        assert m.author == "builtin"
        assert m.platform == ["darwin", "win32"]

    def test_missing_name_raises(self):
        with pytest.raises(ValueError, match="name"):
            parse_manifest({})

    def test_full_manifest(self):
        m = parse_manifest(FULL_MANIFEST)
        assert m.name == "screen"
        assert m.display_name == "Screen Capture"
        assert m.entrypoint == "screen_source:ScreenSource"

        # Events
        assert "screen_frame" in m.events
        assert m.events["screen_frame"].label == "Screen Frame"
        assert m.events["screen_frame"].color == "blue"

        # DB
        assert m.db.table == "screen_data"
        assert "timestamp" in m.db.columns
        assert m.db.columns["timestamp"] == "timestamptz not null"
        assert m.db.indexes == ["processed", "timestamp"]

        # UI
        assert m.ui.icon == "monitor"
        assert "timestamp" in m.ui.visible_columns
        assert "app_name" in m.ui.searchable_columns
        assert m.ui.detail_columns == ["image_path"]

        # Context
        assert m.context.description == "Screenshots with OCR text"
        assert "{timestamp}" in m.context.format

        # GC
        assert m.gc.retention_days_default == 14
        assert "{retention_days}" in m.gc.prompt

        # Config
        assert m.config["interval_seconds"].default == 3
        assert m.config["interval_seconds"].type == "number"
        assert m.config["max_width"].default == 1024

    def test_get_default_config(self):
        m = parse_manifest(FULL_MANIFEST)
        defaults = m.get_default_config()
        assert defaults == {
            "interval_seconds": 3,
            "max_width": 1024,
            "webp_quality": 80,
        }

    def test_supports_current_platform(self):
        m = parse_manifest({"name": "test", "platform": ["darwin"]})
        import sys
        if sys.platform == "darwin":
            assert m.supports_current_platform()
        else:
            assert not m.supports_current_platform()

    def test_unsupported_platform(self):
        m = parse_manifest({"name": "test", "platform": ["nonexistent_os"]})
        assert not m.supports_current_platform()

    def test_empty_sections_default(self):
        m = parse_manifest({"name": "x"})
        assert m.db.table == ""
        assert m.db.columns == {}
        assert m.ui.icon == ""
        assert m.context.format == ""
        assert m.gc.retention_days_default == 14
        assert m.config == {}
        assert m.events == {}


class TestLoadManifest:
    def test_load_from_file(self, tmp_path):
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(FULL_MANIFEST))

        m = load_manifest(manifest_file)
        assert m.name == "screen"
        assert m.source_dir == tmp_path

    def test_load_from_directory(self, tmp_path):
        manifest_file = tmp_path / "manifest.json"
        manifest_file.write_text(json.dumps(MINIMAL_MANIFEST))

        m = load_manifest(tmp_path)
        assert m.name == "test_source"
        assert m.source_dir == tmp_path

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_manifest(tmp_path / "nonexistent.json")

    def test_load_directory_without_manifest_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_manifest(tmp_path / "empty_dir")
