"""Tests for SourcePlugin ABC and ProbeResult."""

import pytest

from source_framework.plugin import SourcePlugin, ProbeResult


class TestProbeResult:
    def test_summary_ok(self):
        r = ProbeResult(
            available=True,
            source="zsh",
            description="found history",
            paths=["/home/user/.zsh_history"],
        )
        s = r.summary()
        assert "[OK]" in s
        assert "zsh" in s
        assert "found history" in s
        assert "/home/user/.zsh_history" in s

    def test_summary_skip(self):
        r = ProbeResult(
            available=False,
            source="chrome",
            description="not running",
            warnings=["Chrome not found"],
        )
        s = r.summary()
        assert "[SKIP]" in s
        assert "chrome" in s
        assert "warn: Chrome not found" in s

    def test_summary_no_extras(self):
        r = ProbeResult(available=True, source="test", description="ok")
        s = r.summary()
        assert s == "[OK] test: ok"


class TestSourcePlugin:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            SourcePlugin()

    def test_concrete_plugin(self):
        class DummySource(SourcePlugin):
            def probe(self) -> ProbeResult:
                return ProbeResult(available=True, source="dummy", description="ok")

            def collect(self) -> list[dict]:
                return [{"timestamp": "2026-01-01T00:00:00Z", "data": "test"}]

        plugin = DummySource()
        result = plugin.probe()
        assert result.available
        assert result.source == "dummy"

        records = plugin.collect()
        assert len(records) == 1
        assert records[0]["data"] == "test"

    def test_missing_probe_raises(self):
        with pytest.raises(TypeError):
            class BadSource(SourcePlugin):
                def collect(self) -> list[dict]:
                    return []
            BadSource()

    def test_missing_collect_raises(self):
        with pytest.raises(TypeError):
            class BadSource(SourcePlugin):
                def probe(self) -> ProbeResult:
                    return ProbeResult(available=True, source="x", description="x")
            BadSource()
