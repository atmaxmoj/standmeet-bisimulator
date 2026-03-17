"""Snapshot tool — capture frames from running Observer API into a fixture file.

Usage: PYTHONPATH=src uv run python tests/experiments/snapshot.py [frame_limit]
Saves to tests/experiments/fixtures/frames.json
"""

import json
import sys
from pathlib import Path

import httpx

API = "http://localhost:5001"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 50

    print(f"Fetching {limit} frames from {API}...")
    frames = httpx.get(f"{API}/capture/frames", params={"limit": limit}, timeout=10).json()["frames"]
    audio = httpx.get(f"{API}/capture/audio", params={"limit": 20}, timeout=10).json()["audio"]
    events = httpx.get(f"{API}/capture/os-events", params={"limit": 30}, timeout=10).json()["events"]

    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    out = FIXTURES_DIR / "frames.json"
    out.write_text(json.dumps({
        "frames": frames,
        "audio": audio,
        "os_events": events,
    }, indent=2, ensure_ascii=False))

    print(f"Saved: {len(frames)} frames, {len(audio)} audio, {len(events)} events → {out}")


if __name__ == "__main__":
    main()
