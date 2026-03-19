# Observer

Behavioral distillation engine. Observes screen activity, identifies tasks, and distills behavioral patterns into Playbook entries.

## Architecture

3-layer cost-optimized pipeline:
1. **Rules filter** ($0) — drop noise apps, short text
2. **Haiku task-level** (~$0.01/episode) — identify tasks within time windows
3. **Opus daily** (~$1-2/run) — distill patterns into Playbook entries + Routines

### Source Plugin System

All data collection via **source plugins** under `sources/builtin/`. Each source:
- Independent process with own venv and dependencies
- `manifest.json` — declares DB schema, UI config, context format, GC policy
- `src/` — SourcePlugin subclass (probe + collect)

7 builtin sources: `screen`, `audio`, `zsh`, `bash`, `safari`, `chrome`, `oslog`

Data flow: source daemon → `POST /ingest/{source_name}` → PostgreSQL manifest table → Huey pipeline

### Engine (Docker)

- FastAPI + Huey task queue + PostgreSQL
- ManifestRegistry scans `sources/builtin/` at startup, creates tables, registers sources
- Unified endpoints: `/ingest/{name}`, `/sources/{name}/data`, `/engine/sources`
- Dashboard dynamically renders panels from manifest metadata

## Running

```bash
npm run setup     # first time: install deps + build images
npm start         # start 7 source plugins + Docker (engine + web + db)
npm stop          # stop everything
npm run status    # check health
npm run logs      # Docker logs
npm test          # lint + pytest (Docker) + framework tests + Playwright e2e
```

Only env var needed: `ANTHROPIC_API_KEY` in `.env`.

## Key Rules

- **PostgreSQL only.** No SQLite anywhere in engine code (Huey queue is the sole exception).
- **Logging must be abundant.** Every significant step needs a debug log.
- **Reuse existing infrastructure.** `app.state.llm`, `app.state.db`, `app.state.manifest_registry`.
- **Large changes: explain the plan first.** Describe design, wait for confirmation.
- **New UI features need Playwright critical-path tests.**
- **Tests in Docker.** `Dockerfile.test` + `docker-compose.test.yml`. Don't run tests on host.
- Commit messages in English only, no Chinese.
- Models hardcoded in `config.py`. DO NOT swap — Haiku on task-level keeps costs ~$0.

## Structure

```
sources/
├── framework/                 # SourcePlugin ABC, manifest loader, EngineClient, runner
│   └── src/source_framework/  # Zero-dependency framework package
└── builtin/                   # 7 source plugins (each with own pyproject.toml + venv)
    ├── screen/                # Screenshot + OCR (pyobjc/mss)
    ├── audio/                 # Microphone + Faster Whisper
    ├── zsh/                   # Zsh history file tracking
    ├── bash/                  # Bash history
    ├── safari/                # Safari tab URL (AppleScript)
    ├── chrome/                # Chrome tab URL (AppleScript)
    └── oslog/                 # macOS log stream (ijson)

src/engine/
├── config.py                  # Settings + model constants
├── main.py                    # FastAPI app + lifespan (ManifestRegistry init)
├── api/routes.py              # Ingest, query, engine management, chat
├── etl/
│   ├── entities.py            # Frame dataclass
│   ├── filter.py              # Noise filter + window detection
│   ├── repository.py          # DB access (legacy ORM + manifest raw SQL)
│   └── sources/
│       ├── base.py            # CaptureSource ABC
│       └── manifest_registry.py  # Scanning, table creation, ingest/query, global singleton
├── pipeline/
│   ├── orchestrator.py        # Episode/distill/routine orchestration
│   ├── stages/                # extract, distill, compose, validate
│   ├── budget.py              # Daily cost cap
│   └── decay.py               # Confidence decay
├── scheduler/tasks.py         # Huey: on_new_data, process_episode, daily cron jobs
├── agents/                    # MCP tools for agentic distill/compose/GC
├── storage/                   # PostgreSQL models, async DB, sync session
└── llm/                       # LLM client (Anthropic + OpenAI-compatible)

web/src/
├── App.tsx                    # Dynamic sidebar from /engine/sources
├── components/
│   ├── SourceDataPanel.tsx    # Generic panel for any manifest source
│   └── ...                    # Episodes, Playbooks, Routines, Usage, Logs, Chat
└── lib/api.ts                 # API client

scripts/
└── migrate_to_source_tables.py  # One-time migration from old tables
```

## Testing

```bash
npm test                       # Full suite (lint + pytest + Playwright)
```

- Engine pytest runs in Docker (`Dockerfile.test` + `docker-compose.test.yml`)
- Source framework tests run locally (`sources/framework/tests/`)
- Playwright e2e runs in Docker (chromium container)
- `tests/conftest.py`: session-scoped PG schema, TRUNCATE RESTART IDENTITY between tests
