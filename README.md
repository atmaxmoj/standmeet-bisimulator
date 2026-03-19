# Observer

Behavioral distillation engine. Observes what you do on your computer — screen, audio, shell commands, browser tabs, system events — identifies discrete tasks, and distills recurring behavioral patterns into a Playbook.

## How it works

```
┌─────────────────────────────────────┐
│  Source Plugins (host, 7 processes) │
│  screen · audio · zsh · bash        │
│  safari · chrome · oslog            │
└───────────────┬─────────────────────┘
                │ HTTP POST /ingest/{source}
┌───────────────▼─────────────────────┐
│  Engine (Docker)                     │
│                                      │
│  Ingest → Window Detection           │
│       → Episode Extraction (Haiku)   │
│       → Playbook Distillation (Opus) │
│       → Routine Composition (Opus)   │
└───────────────┬─────────────────────┘
                │
┌───────────────▼─────────────────────┐
│  Dashboard (Docker, port 5174)       │
│  Sources · Episodes · Playbooks      │
│  Routines · Usage · Chat · Manage    │
└─────────────────────────────────────┘
```

### Cost model

| Layer | Model | Cost | Frequency |
|-------|-------|------|-----------|
| Noise filter | Rules | $0 | Every ingest |
| Episode extraction | Haiku | ~$0.01/episode | On idle gap (5 min) |
| Playbook distillation | Opus | ~$1-2/run | Daily 3am |
| Routine composition | Opus | ~$1-2/run | Daily 3:30am |
| Garbage collection | Opus | ~$0.5/run | Daily 4am |

Daily budget cap: configurable via dashboard (default $10).

## Quick start

```bash
# Prerequisites: Docker, uv, Node.js
npm run setup     # install deps + build images
npm start         # start everything (7 source plugins + Docker containers)
npm run status    # check what's running
```

One env var needed: create `.env` with `ANTHROPIC_API_KEY=sk-ant-...`

Dashboard at http://localhost:5174, API at http://localhost:5001.

## Commands

```bash
npm start         # start source plugins + engine + web
npm stop          # stop everything
npm run restart   # stop + start
npm run status    # show running processes
npm run logs      # docker compose logs
npm test          # lint + engine pytest (Docker) + source framework tests + Playwright e2e
npm run rebuild   # rebuild Docker images
npm run watchdog  # install launchd auto-restart (macOS)
```

## Source plugin system

All data collection is done by **source plugins** — independent processes that capture data and push it to the engine via HTTP.

### Builtin sources

| Source | What it captures | Platform |
|--------|------------------|----------|
| `screen` | Screenshots + OCR of all displays | macOS, Windows |
| `audio` | Microphone recording + Faster Whisper transcription | macOS, Windows |
| `zsh` | Shell command history | macOS |
| `bash` | Shell command history | macOS, Windows |
| `safari` | Active tab URL via AppleScript | macOS |
| `chrome` | Active tab URL via AppleScript | macOS |
| `oslog` | System events (app launch/quit, sleep/wake) via `log stream` | macOS |

### Writing a source plugin

Create a directory under `sources/builtin/` (or `~/.observer/plugins/` for third-party):

```
my_source/
├── manifest.json      # Schema, UI, context format, GC policy
├── pyproject.toml     # Dependencies (includes source-framework)
└── src/my_source/
    └── __init__.py    # SourcePlugin subclass
```

**manifest.json** declares everything the engine needs to know — DB table schema, which columns to show in the dashboard, how to format data for LLM context, and garbage collection policy.

**`__init__.py`** implements two methods:

```python
from source_framework.plugin import SourcePlugin, ProbeResult

class MySource(SourcePlugin):
    def probe(self) -> ProbeResult:
        """Can this source run on the current system?"""
        return ProbeResult(available=True, source="my_source", description="ok")

    def collect(self) -> list[dict]:
        """Return new records. Keys match manifest db.columns."""
        return [{"timestamp": "...", "data": "..."}]
```

The default `start()` method polls `collect()` every `interval_seconds`. Override `start()` for streaming sources (audio, oslog).

Drop the directory in place and `npm run restart` — the engine auto-creates the DB table, the CLI starts the process, and the dashboard shows a new panel.

## Architecture

```
sources/
├── framework/              # SourcePlugin ABC, manifest loader, EngineClient, runner
└── builtin/                # 7 builtin source plugins (each with own venv)

src/engine/
├── api/routes.py           # REST: ingest, query, engine management, chat
├── etl/
│   ├── entities.py         # Frame dataclass (unified observation)
│   ├── filter.py           # Noise filter + window detection
│   ├── repository.py       # DB access (legacy + manifest tables)
│   └── sources/
│       ├── base.py         # CaptureSource ABC
│       └── manifest_registry.py  # Manifest scanning, table creation, ingest/query
├── pipeline/
│   ├── orchestrator.py     # Episode extraction, distillation, routine composition
│   ├── stages/             # extract, distill, compose, validate
│   ├── budget.py           # Daily cost cap
│   └── decay.py            # Confidence decay over time
├── scheduler/tasks.py      # Huey task queue (on_new_data, process_episode, daily cron)
├── agents/                 # Agent SDK tools for agentic distill/compose/GC
├── storage/                # PostgreSQL models, async/sync DB, session utilities
├── llm/                    # LLM client abstraction (Anthropic, OpenAI-compatible)
└── config.py               # Settings, model constants, pricing

web/src/
├── App.tsx                 # Dynamic sidebar from /engine/sources
├── components/
│   ├── SourceDataPanel.tsx # Generic panel for any manifest source
│   ├── EpisodesPanel.tsx   # Task-level summaries
│   ├── PlaybooksPanel.tsx  # Behavioral patterns
│   ├── RoutinesPanel.tsx   # Multi-step sequences
│   ├── UsagePanel.tsx      # LLM cost tracking
│   ├── LogsPanel.tsx       # Pipeline execution logs
│   └── ManagePanel.tsx     # Chat + system controls
└── lib/api.ts              # API client
```

## Data flow

1. Source plugin calls `collect()` → returns records
2. Framework pushes to `POST /ingest/{source_name}`
3. Engine inserts into source's manifest-declared table
4. Huey `on_new_data` loads unprocessed frames from all source tables
5. Noise filter drops trivial data, window detector groups by time
6. Complete windows (30min span or 5min idle gap) → `process_episode`
7. Haiku extracts episodes (task summaries) from frame context
8. Daily: Opus distills episodes into Playbook entries
9. Daily: Opus composes Playbook entries into Routines
10. Daily: GC agent decays confidence, purges old data, audits evidence

## Testing

All tests run in Docker (PostgreSQL). No host dependencies needed beyond Docker + uv.

```bash
npm test              # everything: lint + pytest + Playwright
npm run test:sources  # source framework unit tests only
```

Test infrastructure:
- `Dockerfile.test` — engine test image with pytest
- `docker-compose.test.yml` — test DB + pytest runner + Playwright
- `tests/conftest.py` — session-scoped PG schema, TRUNCATE between tests

## License

Private.
