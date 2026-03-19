"""Tests for os_log parser and classifier (runs locally, no macOS needed)."""

import io
import time

from capture.collectors.oslog_macos import (
    parse_json_stream,
    classify_event,
    format_event,
    OsLogCollector,
)


# ── JSON parser ──


class TestParseJsonStream:
    def test_first_entry(self):
        line = '[{"eventMessage": "hello", "subsystem": "test"}'
        result = parse_json_stream(line)
        assert result == {"eventMessage": "hello", "subsystem": "test"}

    def test_middle_entry(self):
        line = ',{"eventMessage": "world", "subsystem": "test"}'
        result = parse_json_stream(line)
        assert result == {"eventMessage": "world", "subsystem": "test"}

    def test_trailing_comma(self):
        line = '{"eventMessage": "trailing", "subsystem": "test"},'
        result = parse_json_stream(line)
        assert result == {"eventMessage": "trailing", "subsystem": "test"}

    def test_last_entry(self):
        line = '{"eventMessage": "last", "subsystem": "test"}]'
        result = parse_json_stream(line)
        assert result == {"eventMessage": "last", "subsystem": "test"}

    def test_combined_delimiters(self):
        line = ',{"eventMessage": "mid", "subsystem": "test"},'
        result = parse_json_stream(line)
        assert result == {"eventMessage": "mid", "subsystem": "test"}

    def test_empty_line(self):
        assert parse_json_stream("") is None

    def test_array_open(self):
        assert parse_json_stream("[") is None

    def test_array_close(self):
        assert parse_json_stream("]") is None

    def test_filter_header(self):
        """log stream prints a filter description line first."""
        line = 'Filtering the log data using "subsystem == ..."'
        assert parse_json_stream(line) is None

    def test_invalid_json(self):
        assert parse_json_stream("{broken json") is None

    def test_real_format_entry(self):
        """Real entry format from `log stream --style json`."""
        line = '{"timezoneName":"","messageType":"Default","eventType":"logEvent","subsystem":"com.apple.runningboard","category":"process","eventMessage":"[app<com.apple.Safari>:1234] Now tracking process","processImagePath":"/usr/libexec/runningboardd","timestamp":"2026-03-18 20:25:51.083528-0400","processID":193},'
        result = parse_json_stream(line)
        assert result is not None
        assert result["subsystem"] == "com.apple.runningboard"
        assert "Now tracking" in result["eventMessage"]


# ── Classifier ──


class TestClassifyEvent:
    def test_frontmost_change(self):
        entry = {
            "subsystem": "com.apple.runningboard",
            "eventMessage": "Acquiring assertion: frontmost:12345",
        }
        assert classify_event(entry) == "frontmost_change"

    def test_app_launch(self):
        entry = {
            "subsystem": "com.apple.runningboard",
            "eventMessage": "Now tracking process [app<com.apple.Safari>:1234]",
        }
        assert classify_event(entry) == "app_launch"

    def test_app_quit(self):
        entry = {
            "subsystem": "com.apple.runningboard",
            "eventMessage": "[app<com.apple.Safari>:1234] termination reported by proc_exit",
        }
        assert classify_event(entry) == "app_quit"

    def test_noisy_runningboard_ignored(self):
        """Assertions, jetsam, etc. should be ignored."""
        entry = {
            "subsystem": "com.apple.runningboard",
            "eventMessage": "Invalidating assertion some-internal-stuff",
        }
        assert classify_event(entry) is None

    def test_sleep(self):
        entry = {
            "processImagePath": "/usr/libexec/powerd",
            "eventMessage": "sleepWake: Sleep reason: User idle",
        }
        assert classify_event(entry) == "sleep"

    def test_wake(self):
        entry = {
            "processImagePath": "/usr/libexec/powerd",
            "eventMessage": "Wake reason: User activity",
        }
        assert classify_event(entry) == "wake"

    def test_lock(self):
        entry = {
            "processImagePath": "/System/Library/CoreServices/loginwindow.app/Contents/MacOS/loginwindow",
            "eventMessage": "Screen is now locked",
        }
        assert classify_event(entry) == "lock"

    def test_unlock(self):
        entry = {
            "processImagePath": "/System/Library/CoreServices/loginwindow.app/Contents/MacOS/loginwindow",
            "eventMessage": "Screen unlock completed",
        }
        assert classify_event(entry) == "unlock"

    def test_lock_not_unlock(self):
        """'lock' should not match 'unlock'."""
        entry = {
            "processImagePath": "/System/Library/CoreServices/loginwindow.app/Contents/MacOS/loginwindow",
            "eventMessage": "unlock detected",
        }
        # Should be unlock, not lock
        assert classify_event(entry) == "unlock"

    def test_unknown_subsystem(self):
        entry = {
            "subsystem": "com.apple.something.else",
            "eventMessage": "random stuff",
        }
        assert classify_event(entry) is None


# ── Format ──


class TestFormatEvent:
    def test_format(self):
        entry = {
            "processImagePath": "/usr/libexec/runningboardd",
            "eventMessage": "Now tracking process [app<com.apple.Safari>:1234]",
        }
        result = format_event(entry, "app_launch")
        assert "[app_launch]" in result
        assert "runningboardd" in result
        assert "Safari" in result

    def test_long_message_truncated(self):
        entry = {
            "processImagePath": "/usr/bin/test",
            "eventMessage": "x" * 500,
        }
        result = format_event(entry, "test")
        assert len(result) < 400


# ── Collector with fake stream ──


class TestOsLogCollector:
    def _make_stream(self, entries: list[dict]) -> io.StringIO:
        """Create a fake log stream JSON output (pretty-printed, like real `log stream`)."""
        import json as _json
        parts = []
        for i, entry in enumerate(entries):
            prefix = "[" if i == 0 else ","
            parts.append(prefix + _json.dumps(entry, indent=2))
        parts.append("]")
        return io.StringIO("\n".join(parts) + "\n")

    def test_collect_from_stream(self):
        stream = self._make_stream([
            {
                "subsystem": "com.apple.runningboard",
                "eventMessage": "Now tracking process [app<com.apple.Safari>:1234]",
                "processImagePath": "/usr/libexec/runningboardd",
                "timestamp": "2026-03-18 20:25:51.000000-0400",
            },
            {
                "subsystem": "com.apple.runningboard",
                "eventMessage": "Acquiring assertion: frontmost:5678",
                "processImagePath": "/usr/libexec/runningboardd",
                "timestamp": "2026-03-18 20:25:52.000000-0400",
            },
        ])

        collector = OsLogCollector(stdin=stream)
        time.sleep(0.1)  # Let reader thread process
        events = collector.collect()

        assert len(events) == 2
        assert "[app_launch]" in events[0]
        assert "[frontmost_change]" in events[1]

    def test_noisy_events_filtered(self):
        stream = self._make_stream([
            {
                "subsystem": "com.apple.runningboard",
                "eventMessage": "Invalidating assertion blah",
                "processImagePath": "/usr/libexec/runningboardd",
                "timestamp": "2026-03-18 20:25:51.000000-0400",
            },
            {
                "subsystem": "com.apple.runningboard",
                "eventMessage": "is not RunningBoard jetsam managed",
                "processImagePath": "/usr/libexec/runningboardd",
                "timestamp": "2026-03-18 20:25:52.000000-0400",
            },
        ])

        collector = OsLogCollector(stdin=stream)
        time.sleep(0.1)
        events = collector.collect()

        assert len(events) == 0

    def test_mixed_events(self):
        stream = self._make_stream([
            {
                "subsystem": "com.apple.runningboard",
                "eventMessage": "Now tracking process [app<com.apple.Safari>:1]",
                "processImagePath": "/usr/libexec/runningboardd",
                "timestamp": "1",
            },
            {
                "processImagePath": "/usr/libexec/powerd",
                "eventMessage": "sleepWake: Sleep reason: Idle",
                "subsystem": "",
                "timestamp": "2",
            },
            {
                "processImagePath": "/System/Library/CoreServices/loginwindow.app/Contents/MacOS/loginwindow",
                "eventMessage": "Screen is now locked",
                "subsystem": "",
                "timestamp": "3",
            },
            {
                "subsystem": "com.apple.runningboard",
                "eventMessage": "some jetsam noise",
                "processImagePath": "/usr/libexec/runningboardd",
                "timestamp": "4",
            },
        ])

        collector = OsLogCollector(stdin=stream)
        time.sleep(0.1)
        events = collector.collect()

        assert len(events) == 3
        assert "[app_launch]" in events[0]
        assert "[sleep]" in events[1]
        assert "[lock]" in events[2]

    def test_empty_stream(self):
        stream = io.StringIO("[]\n")
        collector = OsLogCollector(stdin=stream)
        time.sleep(0.1)
        events = collector.collect()
        assert events == []

    def test_collect_drains_buffer(self):
        stream = self._make_stream([
            {
                "subsystem": "com.apple.runningboard",
                "eventMessage": "Now tracking process [app<X>:1]",
                "processImagePath": "/usr/libexec/runningboardd",
                "timestamp": "1",
            },
        ])
        collector = OsLogCollector(stdin=stream)
        time.sleep(0.1)

        first = collector.collect()
        assert len(first) == 1

        second = collector.collect()
        assert len(second) == 0
