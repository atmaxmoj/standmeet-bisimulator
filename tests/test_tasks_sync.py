"""E2E tests for Huey sync pipeline (tasks.py).

Tests the same pipeline as test_pipeline_e2e.py but through the sync code path
that production Huey tasks use. Mock LLM, real sqlite3 DB.
"""

import json
import sqlite3

import pytest

from engine.llm import LLMResponse
from engine.pipeline.collector import Frame
from engine.pipeline.episode import EPISODE_PROMPT, build_context
from engine.pipeline.distill import DISTILL_PROMPT
from engine.pipeline.routines import ROUTINE_PROMPT
from engine.pipeline.validate import validate_episodes, validate_playbooks, with_retry

# Same canned responses as test_pipeline_e2e.py
EPISODE_LLM_RESPONSE = json.dumps([
    {
        "summary": "Edited Python code in VSCode",
        "method": "sequential editing",
        "turning_points": ["switched approach"],
        "avoidance": ["did not use debugger"],
        "under_pressure": False,
        "apps": ["VSCode"],
        "started_at": "2026-03-16T10:00:00Z",
        "ended_at": "2026-03-16T10:04:00Z",
    },
    {
        "summary": "Ran tests after editing",
        "method": "test-after-edit",
        "turning_points": [],
        "avoidance": [],
        "under_pressure": False,
        "apps": ["Terminal"],
        "started_at": "2026-03-16T10:04:00Z",
        "ended_at": "2026-03-16T10:05:00Z",
    },
])

DISTILL_LLM_RESPONSE = json.dumps([
    {
        "name": "edit-then-test",
        "context": "After code changes",
        "intuition": "Run tests",
        "action": "Execute test suite",
        "why": "Catch regressions",
        "counterexample": None,
        "confidence": 0.7,
        "maturity": "developing",
        "evidence": [1, 2],
    },
])

ROUTINE_LLM_RESPONSE = json.dumps([
    {
        "name": "code-edit-cycle",
        "trigger": "Starting coding task",
        "goal": "Implement and verify",
        "steps": ["Open file", "Edit", "IF tests THEN run ELSE skip", "Commit"],
        "uses": ["edit-then-test"],
        "confidence": 0.6,
        "maturity": "nascent",
    },
])

SCHEMA = """
CREATE TABLE frames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL, app_name TEXT DEFAULT '', window_name TEXT DEFAULT '',
    text TEXT DEFAULT '', display_id INTEGER DEFAULT 0,
    image_hash TEXT DEFAULT '', image_path TEXT DEFAULT '',
    processed INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE audio_frames (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL, duration_seconds REAL DEFAULT 0,
    text TEXT DEFAULT '', language TEXT DEFAULT '', source TEXT DEFAULT 'mic',
    chunk_path TEXT DEFAULT '', processed INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE os_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL, event_type TEXT NOT NULL,
    source TEXT DEFAULT '', data TEXT DEFAULT '',
    processed INTEGER DEFAULT 0, created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    summary TEXT NOT NULL, app_names TEXT DEFAULT '', frame_count INTEGER DEFAULT 0,
    started_at TEXT NOT NULL, ended_at TEXT NOT NULL,
    frame_id_min INTEGER DEFAULT 0, frame_id_max INTEGER DEFAULT 0,
    frame_source TEXT DEFAULT '', created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE playbook_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE, context TEXT DEFAULT '', action TEXT DEFAULT '',
    confidence REAL DEFAULT 0, maturity TEXT DEFAULT 'nascent',
    evidence TEXT DEFAULT '[]', last_evidence_at TEXT,
    created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE routines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE, trigger TEXT DEFAULT '', goal TEXT DEFAULT '',
    steps TEXT DEFAULT '[]', uses TEXT DEFAULT '[]',
    confidence REAL DEFAULT 0, maturity TEXT DEFAULT 'nascent',
    created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE token_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model TEXT NOT NULL, layer TEXT NOT NULL,
    input_tokens INTEGER DEFAULT 0, output_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0, created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE pipeline_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage TEXT NOT NULL, prompt TEXT DEFAULT '', response TEXT DEFAULT '',
    model TEXT DEFAULT '', input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0, cost_usd REAL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


@pytest.fixture
def conn(tmp_path):
    db_path = str(tmp_path / "test.db")
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA)
    yield c
    c.close()


def _seed_frames(conn, n=5):
    """Insert screen frames and return their IDs."""
    ids = []
    for i in range(n):
        conn.execute(
            "INSERT INTO frames (timestamp, app_name, window_name, text, display_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (f"2026-03-16T10:{i:02d}:00Z", "VSCode", "editor.py", f"def func_{i}(): pass", 1),
        )
        ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    conn.commit()
    return ids


def _seed_os_events(conn, n=2):
    ids = []
    for i in range(n):
        conn.execute(
            "INSERT INTO os_events (timestamp, event_type, source, data) VALUES (?, ?, ?, ?)",
            (f"2026-03-16T10:{i:02d}:30Z", "shell_command", "zsh", f"git status {i}"),
        )
        ids.append(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    conn.commit()
    return ids


def _seed_episodes(conn):
    """Insert episodes (as if process_episode already ran)."""
    for task in json.loads(EPISODE_LLM_RESPONSE):
        summary = json.dumps({
            "summary": task["summary"], "method": task["method"],
            "turning_points": task["turning_points"],
            "avoidance": task["avoidance"], "under_pressure": task["under_pressure"],
        }, ensure_ascii=False)
        conn.execute(
            "INSERT INTO episodes (summary, app_names, frame_count, started_at, ended_at, "
            "frame_id_min, frame_id_max, frame_source) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (summary, json.dumps(task["apps"]), 5, task["started_at"], task["ended_at"], 1, 5, "capture"),
        )
    conn.commit()


class MockSyncLLM:
    """Sync LLM that returns canned responses."""
    def __init__(self, responses):
        self._responses = list(responses)
        self._idx = 0
        self.calls = []

    def complete(self, prompt, model):
        self.calls.append(prompt)
        text = self._responses[self._idx % len(self._responses)]
        self._idx += 1
        return LLMResponse(text=text, input_tokens=100, output_tokens=50)


def _load_frames_sync(conn, screen_ids, os_event_ids=None):
    """Same logic as tasks._load_frames but importable without side effects."""
    frames = []
    if screen_ids:
        ph = ",".join("?" * len(screen_ids))
        rows = conn.execute(
            f"SELECT id, timestamp, app_name, window_name, text, image_path "
            f"FROM frames WHERE id IN ({ph}) ORDER BY timestamp", screen_ids,
        ).fetchall()
        frames.extend(Frame(id=r["id"], source="capture", text=r["text"] or "",
                            app_name=r["app_name"] or "", window_name=r["window_name"] or "",
                            timestamp=r["timestamp"] or "", image_path=r["image_path"] or "")
                      for r in rows)
    if os_event_ids:
        ph = ",".join("?" * len(os_event_ids))
        rows = conn.execute(
            f"SELECT id, timestamp, event_type, source, data "
            f"FROM os_events WHERE id IN ({ph}) ORDER BY timestamp", os_event_ids,
        ).fetchall()
        frames.extend(Frame(id=r["id"], source="os_event", text=r["data"] or "",
                            app_name=r["event_type"] or "", window_name=r["source"] or "",
                            timestamp=r["timestamp"] or "")
                      for r in rows)
    frames.sort(key=lambda f: f.timestamp)
    return frames


def _store_episodes_sync(conn, tasks, frames):
    """Same logic as tasks._store_episodes."""
    fmin = min(f.id for f in frames)
    fmax = max(f.id for f in frames)
    fsource = ",".join(sorted({f.source for f in frames}))
    for task in tasks:
        summary = json.dumps({
            "summary": task.get("summary", ""), "method": task.get("method", ""),
            "turning_points": task.get("turning_points", []),
            "avoidance": task.get("avoidance", []),
            "under_pressure": task.get("under_pressure", False),
        }, ensure_ascii=False)
        conn.execute(
            "INSERT INTO episodes (summary, app_names, frame_count, started_at, ended_at, "
            "frame_id_min, frame_id_max, frame_source) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (summary, json.dumps(task.get("apps", [])), len(frames),
             task.get("started_at", frames[0].timestamp),
             task.get("ended_at", frames[-1].timestamp), fmin, fmax, fsource),
        )


# ── Load frames ──

class TestLoadFrames:
    def test_loads_screen_frames(self, conn):
        ids = _seed_frames(conn, 3)
        frames = _load_frames_sync(conn, ids)
        assert len(frames) == 3
        assert frames[0].app_name == "VSCode"
        assert frames[0].source == "capture"

    def test_loads_os_events(self, conn):
        os_ids = _seed_os_events(conn, 2)
        frames = _load_frames_sync(conn, [], os_ids)
        assert len(frames) == 2
        assert frames[0].source == "os_event"
        assert "git status" in frames[0].text

    def test_mixed_sources_sorted_by_timestamp(self, conn):
        screen_ids = _seed_frames(conn, 2)
        os_ids = _seed_os_events(conn, 2)
        frames = _load_frames_sync(conn, screen_ids, os_ids)
        assert len(frames) == 4
        timestamps = [f.timestamp for f in frames]
        assert timestamps == sorted(timestamps)

    def test_empty_ids_returns_empty(self, conn):
        assert _load_frames_sync(conn, []) == []


# ── Build prompt ──

class TestBuildPrompt:
    def test_contains_frame_data(self):
        frames = [Frame(id=1, source="capture", timestamp="2026-03-16T10:00:00Z",
                        app_name="VSCode", window_name="test.py", text="hello world")]
        context = build_context(frames)
        prompt = EPISODE_PROMPT.format(context=context)
        assert "hello world" in prompt
        assert "VSCode" in prompt
        assert "{context}" not in prompt


# ── Store episodes ──

class TestStoreEpisodes:
    def test_stores_to_db(self, conn):
        tasks = json.loads(EPISODE_LLM_RESPONSE)
        frames = [Frame(id=i, source="capture", timestamp=f"2026-03-16T10:{i:02d}:00Z",
                        app_name="VSCode", window_name="x", text="x") for i in range(1, 6)]
        _store_episodes_sync(conn, tasks, frames)
        conn.commit()
        rows = conn.execute("SELECT * FROM episodes").fetchall()
        assert len(rows) == 2
        assert rows[0]["frame_id_min"] == 1
        assert rows[0]["frame_id_max"] == 5


# ── Full sync episode pipeline ──

class TestProcessEpisodeSync:
    def test_full_sync_chain(self, conn):
        """frames in DB → load → build prompt → LLM → validate → store."""
        screen_ids = _seed_frames(conn, 5)
        frames = _load_frames_sync(conn, screen_ids, [])
        prompt = EPISODE_PROMPT.format(context=build_context(frames))

        llm = MockSyncLLM([EPISODE_LLM_RESPONSE])
        resp = llm.complete(prompt, "haiku")
        tasks = validate_episodes(resp.text)
        _store_episodes_sync(conn, tasks, frames)
        conn.commit()

        episodes = conn.execute("SELECT * FROM episodes").fetchall()
        assert len(episodes) == 2
        assert "VSCode" in json.loads(episodes[0]["summary"])["summary"]
        assert llm.calls[0] == prompt

    def test_with_retry_on_valid_response(self, conn):
        """with_retry should pass through valid responses."""
        llm = MockSyncLLM([EPISODE_LLM_RESPONSE])
        last_resp = [None]

        def call(retry_prompt):
            resp = llm.complete(retry_prompt or "test", "haiku")
            last_resp[0] = resp
            return resp.text

        tasks = with_retry(call, validate_episodes)
        assert len(tasks) == 2


# ── Full sync distill pipeline ──

class TestDistillSync:
    def test_full_sync_distill(self, conn):
        """episodes in DB → format prompt → LLM → validate → store playbook."""
        _seed_episodes(conn)

        episodes = conn.execute(
            "SELECT * FROM episodes ORDER BY created_at"
        ).fetchall()
        episodes_text = "\n\n".join(
            f"Episode #{e['id']}:\n{e['summary']}" for e in episodes
        )
        playbooks_text = "(none yet)"
        prompt = DISTILL_PROMPT.format(playbooks=playbooks_text, episodes=episodes_text)

        llm = MockSyncLLM([DISTILL_LLM_RESPONSE])
        resp = llm.complete(prompt, "opus")
        entries = validate_playbooks(resp.text)

        for entry in entries:
            conn.execute(
                "INSERT INTO playbook_entries (name, context, action, confidence, maturity, evidence) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (entry["name"], entry.get("context", ""), entry.get("action", ""),
                 entry["confidence"], entry["maturity"], json.dumps(entry.get("evidence", []))),
            )
        conn.commit()

        playbooks = conn.execute("SELECT * FROM playbook_entries").fetchall()
        assert len(playbooks) == 1
        assert playbooks[0]["name"] == "edit-then-test"
        assert playbooks[0]["confidence"] == 0.7

    def test_distill_prompt_includes_existing_playbooks(self, conn):
        """Second distill should include existing entries in prompt."""
        _seed_episodes(conn)
        conn.execute(
            "INSERT INTO playbook_entries (name, context, action, confidence, maturity, evidence) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("existing-rule", "some context", "some action", 0.5, "nascent", "[]"),
        )
        conn.commit()

        existing = conn.execute("SELECT * FROM playbook_entries").fetchall()
        playbooks_text = "\n".join(f"- {p['name']}" for p in existing)

        assert "existing-rule" in playbooks_text


# ── Full sync routine pipeline ──

class TestRoutineSync:
    def test_full_sync_routine(self, conn):
        """episodes + playbook in DB → format prompt → LLM → parse → store routine."""
        _seed_episodes(conn)
        conn.execute(
            "INSERT INTO playbook_entries (name, context, action, confidence, maturity, evidence) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("edit-then-test", "After changes", "Run tests", 0.7, "developing", "[1,2]"),
        )
        conn.commit()

        episodes = conn.execute("SELECT * FROM episodes").fetchall()
        playbooks = conn.execute("SELECT * FROM playbook_entries").fetchall()

        episodes_text = "\n".join(f"Episode #{e['id']}:\n{e['summary']}" for e in episodes)
        playbooks_text = "\n".join(f"- {p['name']}" for p in playbooks)
        routines_text = "(none yet)"

        prompt = ROUTINE_PROMPT.format(
            playbooks=playbooks_text, routines=routines_text, episodes=episodes_text,
        )

        llm = MockSyncLLM([ROUTINE_LLM_RESPONSE])
        resp = llm.complete(prompt, "opus")

        text = resp.text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        entries = json.loads(text)

        for entry in entries:
            conn.execute(
                "INSERT INTO routines (name, trigger, goal, steps, uses, confidence, maturity) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (entry["name"], entry.get("trigger", ""), entry.get("goal", ""),
                 json.dumps(entry.get("steps", [])), json.dumps(entry.get("uses", [])),
                 entry.get("confidence", 0.4), entry.get("maturity", "nascent")),
            )
        conn.commit()

        routines = conn.execute("SELECT * FROM routines").fetchall()
        assert len(routines) == 1
        assert routines[0]["name"] == "code-edit-cycle"
        steps = json.loads(routines[0]["steps"])
        assert len(steps) == 4
        uses = json.loads(routines[0]["uses"])
        assert "edit-then-test" in uses

    def test_routine_prompt_includes_playbooks_and_episodes(self, conn):
        _seed_episodes(conn)
        conn.execute(
            "INSERT INTO playbook_entries (name, context, action, confidence, maturity, evidence) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("my-rule", "ctx", "act", 0.5, "nascent", "[]"),
        )
        conn.commit()

        episodes = conn.execute("SELECT * FROM episodes").fetchall()
        playbooks = conn.execute("SELECT * FROM playbook_entries").fetchall()

        episodes_text = "\n".join(f"Episode #{e['id']}:\n{e['summary']}" for e in episodes)
        playbooks_text = "\n".join(f"- {p['name']}" for p in playbooks)

        prompt = ROUTINE_PROMPT.format(
            playbooks=playbooks_text, routines="(none)", episodes=episodes_text,
        )
        assert "my-rule" in prompt
        assert "Edited Python code" in prompt


# ── Full sync chain L1 → L2 → L3 ──

class TestFullSyncChain:
    def test_frames_to_routines_sync(self, conn):
        """Complete sync chain: seed frames → episode → distill → routine."""
        # L1: Frames → Episodes
        screen_ids = _seed_frames(conn, 5)
        frames = _load_frames_sync(conn, screen_ids, [])
        prompt = EPISODE_PROMPT.format(context=build_context(frames))
        llm1 = MockSyncLLM([EPISODE_LLM_RESPONSE])
        tasks = validate_episodes(llm1.complete(prompt, "haiku").text)
        _store_episodes_sync(conn, tasks, frames)
        conn.commit()

        # L2: Episodes → Playbook
        episodes = conn.execute("SELECT * FROM episodes").fetchall()
        ep_text = "\n".join(f"Episode #{e['id']}:\n{e['summary']}" for e in episodes)
        dist_prompt = DISTILL_PROMPT.format(playbooks="(none)", episodes=ep_text)
        llm2 = MockSyncLLM([DISTILL_LLM_RESPONSE])
        entries = validate_playbooks(llm2.complete(dist_prompt, "opus").text)
        for entry in entries:
            conn.execute(
                "INSERT INTO playbook_entries (name, context, action, confidence, maturity, evidence) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (entry["name"], entry.get("context", ""), entry.get("action", ""),
                 entry["confidence"], entry["maturity"], json.dumps(entry.get("evidence", []))),
            )
        conn.commit()

        # L3: Episodes + Playbook → Routines
        playbooks = conn.execute("SELECT * FROM playbook_entries").fetchall()
        pb_text = "\n".join(f"- {p['name']}" for p in playbooks)
        rtn_prompt = ROUTINE_PROMPT.format(playbooks=pb_text, routines="(none)", episodes=ep_text)
        llm3 = MockSyncLLM([ROUTINE_LLM_RESPONSE])
        text = llm3.complete(rtn_prompt, "opus").text
        rtn_entries = json.loads(text)
        for entry in rtn_entries:
            conn.execute(
                "INSERT INTO routines (name, trigger, goal, steps, uses, confidence, maturity) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (entry["name"], entry.get("trigger", ""), entry.get("goal", ""),
                 json.dumps(entry.get("steps", [])), json.dumps(entry.get("uses", [])),
                 entry.get("confidence", 0.4), entry.get("maturity", "nascent")),
            )
        conn.commit()

        # Verify all in DB
        assert len(conn.execute("SELECT * FROM episodes").fetchall()) == 2
        assert len(conn.execute("SELECT * FROM playbook_entries").fetchall()) == 1
        routines = conn.execute("SELECT * FROM routines").fetchall()
        assert len(routines) == 1
        assert json.loads(routines[0]["uses"]) == ["edit-then-test"]
