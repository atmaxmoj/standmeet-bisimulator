"""Experiment runner — runs inside Docker container.

Loads a frames fixture, runs multiple prompt variants through the pipeline,
saves each result immediately.

Usage: npm run experiment [-- <fixture_path>]
"""

import json
import logging
import sys
from pathlib import Path

from engine.config import Settings, MODEL_FAST
from engine.infra.llm import create_client
from engine.pipeline.stages.extract import build_context_from_dicts, parse_llm_json

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

RESULTS_DIR = Path("/data/experiment_results")
DEFAULT_FIXTURE = Path("/app/tests/experiments/fixtures/frames.json")


def load_fixture(path: Path) -> dict:
    data = json.loads(path.read_text())
    logger.info("Loaded fixture: %d frames, %d audio, %d events",
                len(data["frames"]), len(data.get("audio", [])), len(data.get("os_events", [])))
    return data


def load_prompts() -> dict[str, str]:
    """Load all prompt variants.

    Convention: files in /app/tests/experiments/prompts/*.txt
    Use {context} as placeholder (NOT Python .format() style).
    Baseline uses the production prompt (auto-converted from .format() style).
    """
    prompts_dir = Path("/app/tests/experiments/prompts")
    result = {}
    if prompts_dir.exists():
        for f in sorted(prompts_dir.glob("*.txt")):
            result[f.stem] = f.read_text()
    # Always include production prompt as baseline, converting {{ → { for .replace() compat
    from engine.domain.prompts.episode import EPISODE_PROMPT
    baseline = EPISODE_PROMPT.replace("{{", "{").replace("}}", "}")
    result.setdefault("baseline", baseline)
    return result


def save(name: str, data: dict):
    path = RESULTS_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    logger.info("Saved → %s", path)


def main():
    fixture_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_FIXTURE
    if not fixture_path.exists():
        logger.error("Fixture not found: %s", fixture_path)
        logger.error("Run: PYTHONPATH=src uv run python tests/experiments/snapshot.py")
        sys.exit(1)

    settings = Settings()
    llm = create_client(
        api_key=settings.anthropic_api_key,
        auth_token=settings.claude_code_oauth_token,
        openai_api_key=settings.openai_api_key,
        openai_base_url=settings.openai_base_url,
    )

    fixture = load_fixture(fixture_path)
    context = build_context_from_dicts(
        fixture["frames"],
        fixture.get("audio", []),
        fixture.get("os_events", []),
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    save("context", {"chars": len(context), "fixture": str(fixture_path)})

    prompts = load_prompts()
    logger.info("Prompt variants: %s", list(prompts.keys()))

    for name, prompt in prompts.items():
        logger.info("Running [%s]...", name)
        try:
            prompt_text = prompt.replace("{context}", context)
            resp = llm.complete(prompt_text, MODEL_FAST)
            episodes = parse_llm_json(resp.text)
            save(name, {
                "episodes": episodes,
                "count": len(episodes),
                "input_tokens": resp.input_tokens,
                "output_tokens": resp.output_tokens,
            })
            logger.info("  [%s] → %d episodes, %d tokens", name, len(episodes), resp.output_tokens)
        except Exception as e:
            save(name, {"error": str(e), "episodes": []})
            logger.exception("  [%s] FAILED", name)

    logger.info("Done. Results in %s", RESULTS_DIR)


if __name__ == "__main__":
    main()
