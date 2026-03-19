# Bisimulator

Behavioral distillation engine. Observes screen activity, identifies tasks, and distills behavioral patterns into Playbook entries.

## Architecture

3-layer pipeline:
1. **Rules filter** ($0) — drop noise apps, short text
2. **Haiku task-level** (~$0.01/episode) — identify tasks within time windows
3. **Opus weekly** (~$1-2/week) — distill patterns into Playbook entries

### Source Plugin System

All data collection is done via **source plugins** under `sources/builtin/`. Each source has:
- `manifest.json` — declares DB schema, UI config, context format, GC policy
- `src/` — source daemon code (Python, uses `source_framework`)

Available sources: `screen`, `audio`, `zsh`, `bash`, `safari`, `chrome`, `oslog`

Data flows: source daemon → `POST /ingest/{source_name}` → manifest-based DB table → ETL pipeline

## Running

```bash
# First time: installs screenpipe + starts everything (macOS & Linux)
make setup

# Daily use
make start          # start screenpipe + docker
make stop           # stop everything
make status         # check health
make logs           # bisimulator logs
```

Only env var needed: `ANTHROPIC_API_KEY` in `.env`.

Set `LOG_LEVEL=DEBUG` (default) for verbose logging, `LOG_LEVEL=INFO` for production.

## Key Rules

- **Logging must be abundant.** Every significant step needs a debug log. When something goes wrong, logs are the first thing to check. If logs are insufficient to diagnose an issue, add more logs before guessing.
- **Reuse existing infrastructure.** Use `app.state.llm` for LLM calls, `app.state.db` for DB access. Check existing interfaces before adding new ones.
- **Large changes: explain the plan first.** For new modules, dependencies, or architecture changes, describe the design in 2-3 sentences and wait for confirmation.
- **New UI features need Playwright critical-path tests.** Not just "panel renders" — test core interactions.
- Commit messages in English only, no Chinese.
- Models are hardcoded in `config.py`. DO NOT swap them — Haiku on task-level keeps costs ~$0, Opus on task-level would cost ~$50/day.

## Structure

```
src/engine/
├── config.py              # Settings + model constants
├── db.py                  # SQLite (episodes, playbook_entries, state)
├── main.py                # FastAPI app + pipeline loop
├── api/routes.py          # REST endpoints
├── etl/
│   ├── entities.py        # Frame dataclass
│   ├── filter.py          # Rules-based noise filter + WindowAccumulator
│   └── sources/           # Source plugin registry + manifest system
│       ├── base.py        # CaptureSource ABC
│       ├── manifest_registry.py  # ManifestRegistry, table creation, ingest/query
│       └── builtin/       # Legacy built-in source adapters
└── pipeline/
    ├── collector.py       # Signal collectors
    ├── episode.py         # Haiku: time window -> episodes
    └── distill.py         # Opus: episodes -> playbook entries

sources/builtin/           # Source plugin manifests + daemons
├── screen/                # Screenshot + OCR
├── audio/                 # Microphone transcription
├── zsh/                   # Zsh history
├── bash/                  # Bash history
├── safari/                # Safari URLs
├── chrome/                # Chrome URLs
└── oslog/                 # macOS system logs

scripts/
└── migrate_to_source_tables.py  # Migrate old tables to manifest-based tables
```
