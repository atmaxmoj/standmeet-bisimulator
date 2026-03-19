"""os_log Docker tests — real log stream from host mounted into container.

Run from repo root:
    # 1. Capture 10s of real os_log:
    timeout 10 log stream --style json --predicate \
      '(subsystem == "com.apple.runningboard") OR
       (process == "powerd" AND eventMessage CONTAINS "sleepWake") OR
       (process == "loginwindow")' > /tmp/oslog_sample.json

    # 2. Mount into container and run:
    docker run --rm -v /tmp/oslog_sample.json:/data/oslog_sample.json \
      probe-test uv run pytest tests/test_oslog_docker.py -xvs
"""

import os
import pytest

from capture.collectors.oslog_macos import (
    parse_json_stream_multiline,
    classify_event,
    format_event,
)

SAMPLE_PATH = os.environ.get("OSLOG_SAMPLE", "/data/oslog_sample.json")


@pytest.fixture(scope="session")
def entries():
    """Read all parseable JSON entries from mounted sample file."""
    if not os.path.exists(SAMPLE_PATH):
        pytest.skip(f"os_log sample not found at {SAMPLE_PATH}")
    with open(SAMPLE_PATH) as f:
        return parse_json_stream_multiline(f)


class TestRealOsLogStream:
    def test_got_entries(self, entries):
        assert len(entries) > 0, "no entries parsed — is log stream piped to stdin?"

    def test_required_fields(self, entries):
        for entry in entries:
            assert "eventMessage" in entry
            assert "timestamp" in entry

    def test_classifier_known_categories(self, entries):
        known = {"app_launch", "app_quit", "frontmost_change", "sleep", "wake", "lock", "unlock"}
        for entry in entries:
            cat = classify_event(entry)
            if cat is not None:
                assert cat in known, f"unknown category: {cat}"

    def test_noise_filtered(self, entries):
        total = len(entries)
        classified = sum(1 for e in entries if classify_event(e) is not None)
        noise_ratio = 1 - (classified / max(total, 1))
        # Most runningboard events are noise
        assert noise_ratio > 0.3 or total < 5, \
            f"too little filtering: {classified}/{total}"

    def test_format_readable(self, entries):
        for entry in entries:
            cat = classify_event(entry)
            if cat is None:
                continue
            formatted = format_event(entry, cat)
            assert f"[{cat}]" in formatted
            assert len(formatted) < 400
