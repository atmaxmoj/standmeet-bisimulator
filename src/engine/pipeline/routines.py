"""Daily: Opus analyzes episodes + playbook entries → routines (composed workflows)."""

import json
import logging

from engine.config import MODEL_DEEP
from engine.db import DB
from engine.llm import LLMClient
from engine.domain.prompts.routine import ROUTINE_PROMPT  # noqa: F401
from engine.pipeline.episode import parse_llm_json
from engine.pipeline.memory_file import write_routine

logger = logging.getLogger(__name__)


async def daily_routines(client: LLMClient, db: DB, prompt_template: str = ROUTINE_PROMPT) -> int:
    """Run daily routine extraction: episodes + playbook → routines."""
    logger.info("starting routine extraction")
    episodes = await db.get_recent_episodes(days=1)
    if not episodes:
        logger.info("no episodes today, skipping routine extraction")
        return 0

    playbooks = await db.get_all_playbooks()
    existing_routines = await db.get_all_routines()

    logger.debug(
        "routine input: %d episodes, %d playbooks, %d existing routines",
        len(episodes), len(playbooks), len(existing_routines),
    )

    episodes_text = "\n\n".join(
        f"Episode #{e['id']} ({e['started_at']} to {e['ended_at']}):\n{e['summary']}"
        for e in episodes
    )

    playbooks_text = (
        "\n".join(
            f"- **{p['name']}** ({p['confidence']:.1f}): {p['context']} → {p['action']}"
            for p in playbooks
        )
        if playbooks
        else "(no playbook entries yet)"
    )

    routines_text = (
        "\n\n".join(
            f"- **{r['name']}** (confidence: {r['confidence']}, maturity: {r['maturity']})\n"
            f"  Trigger: {r['trigger']}\n"
            f"  Goal: {r['goal']}\n"
            f"  Steps: {r['steps']}\n"
            f"  Uses: {r['uses']}"
            for r in existing_routines
        )
        if existing_routines
        else "(none yet)"
    )

    try:
        prompt = prompt_template.format(
            playbooks=playbooks_text,
            routines=routines_text,
            episodes=episodes_text,
        )
        resp = await client.acomplete(prompt, MODEL_DEEP)
        logger.debug("opus response: %d chars", len(resp.text))

        cost_usd = resp.cost_usd or 0
        await db.record_usage(
            model=MODEL_DEEP, layer="routines",
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            cost_usd=cost_usd,
        )
        await db.insert_pipeline_log(
            stage="routines",
            prompt=prompt, response=resp.text, model=MODEL_DEEP,
            input_tokens=resp.input_tokens, output_tokens=resp.output_tokens,
            cost_usd=cost_usd,
        )

        entries = parse_llm_json(resp.text)
        logger.debug("opus returned %d routines", len(entries))

        count = 0
        for entry in entries:
            await db.upsert_routine(
                name=entry["name"],
                trigger=entry.get("trigger", ""),
                goal=entry.get("goal", ""),
                steps=json.dumps(entry.get("steps", []), ensure_ascii=False),
                uses=json.dumps(entry.get("uses", []), ensure_ascii=False),
                confidence=entry.get("confidence", 0.4),
                maturity=entry.get("maturity", "nascent"),
            )
            routines_after = await db.get_all_routines()
            rt = next((r for r in routines_after if r["name"] == entry["name"]), None)
            if rt:
                write_routine(rt)
            count += 1

        logger.info("Routine extraction: %d routines from %d episodes", count, len(episodes))
        return count

    except Exception:
        logger.exception("Routine extraction failed")
        return 0
