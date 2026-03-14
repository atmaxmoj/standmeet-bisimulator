"""Tests for browser URL collectors."""

from unittest.mock import patch, MagicMock
import subprocess

from capture.collectors.browser_macos import (
    ChromeURLCollector,
    SafariURLCollector,
    _is_app_running,
)


class TestIsAppRunning:
    def test_returns_true_when_running(self):
        result = MagicMock()
        result.stdout = "true\n"
        with patch("subprocess.run", return_value=result) as mock_run:
            assert _is_app_running("Safari") is True
            args = mock_run.call_args[0][0]
            assert "osascript" in args

    def test_returns_false_when_not_running(self):
        result = MagicMock()
        result.stdout = "false\n"
        with patch("subprocess.run", return_value=result):
            assert _is_app_running("Safari") is False

    def test_returns_false_on_error(self):
        with patch("subprocess.run", side_effect=Exception("fail")):
            assert _is_app_running("Safari") is False


class TestChromeURLCollector:
    def _make_collector(self):
        return ChromeURLCollector()

    def test_returns_url_when_chrome_running(self):
        """Chrome URL should be captured even when Chrome is not frontmost."""
        collector = self._make_collector()
        running_result = MagicMock()
        running_result.stdout = "true\n"
        url_result = MagicMock()
        url_result.stdout = "https://github.com\n"

        with patch("subprocess.run", side_effect=[running_result, url_result]):
            result = collector.collect()
        assert result == ["https://github.com"]

    def test_skips_when_chrome_not_running(self):
        collector = self._make_collector()
        running_result = MagicMock()
        running_result.stdout = "false\n"

        with patch("subprocess.run", return_value=running_result):
            result = collector.collect()
        assert result == []

    def test_deduplicates_same_url(self):
        collector = self._make_collector()
        running_result = MagicMock()
        running_result.stdout = "true\n"
        url_result = MagicMock()
        url_result.stdout = "https://github.com\n"

        with patch("subprocess.run", side_effect=[running_result, url_result]):
            result1 = collector.collect()
        assert result1 == ["https://github.com"]

        with patch("subprocess.run", side_effect=[running_result, url_result]):
            result2 = collector.collect()
        assert result2 == []  # same URL, should skip

    def test_returns_new_url_after_change(self):
        collector = self._make_collector()
        running_result = MagicMock()
        running_result.stdout = "true\n"
        url1 = MagicMock()
        url1.stdout = "https://github.com\n"
        url2 = MagicMock()
        url2.stdout = "https://google.com\n"

        with patch("subprocess.run", side_effect=[running_result, url1]):
            collector.collect()

        with patch("subprocess.run", side_effect=[running_result, url2]):
            result = collector.collect()
        assert result == ["https://google.com"]

    def test_handles_missing_value(self):
        collector = self._make_collector()
        running_result = MagicMock()
        running_result.stdout = "true\n"
        url_result = MagicMock()
        url_result.stdout = "missing value\n"

        with patch("subprocess.run", side_effect=[running_result, url_result]):
            result = collector.collect()
        assert result == []

    def test_handles_timeout(self):
        collector = self._make_collector()
        running_result = MagicMock()
        running_result.stdout = "true\n"

        with patch("subprocess.run", side_effect=[running_result, subprocess.TimeoutExpired("osascript", 3)]):
            result = collector.collect()
        assert result == []


class TestSafariURLCollector:
    def test_returns_url_when_safari_running(self):
        collector = SafariURLCollector()
        running_result = MagicMock()
        running_result.stdout = "true\n"
        url_result = MagicMock()
        url_result.stdout = "https://apple.com\n"

        with patch("subprocess.run", side_effect=[running_result, url_result]):
            result = collector.collect()
        assert result == ["https://apple.com"]

    def test_skips_when_safari_not_running(self):
        collector = SafariURLCollector()
        running_result = MagicMock()
        running_result.stdout = "false\n"

        with patch("subprocess.run", return_value=running_result):
            result = collector.collect()
        assert result == []
