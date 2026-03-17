"""Daily: Opus analyzes episodes and generates/updates playbook entries."""

import json
import logging

from engine.config import MODEL_DEEP
from engine.db import DB
from engine.llm import LLMClient
from engine.domain.prompts.playbook import PLAYBOOK_PROMPT, DISTILL_PROMPT  # noqa: F401
from engine.pipeline.episode import parse_llm_json
from engine.pipeline.memory_file import write_playbook

logger = logging.getLogger(__name__)


async def daily_distill(
    client: LLMClient,
    db: DB,
    prompt_template: str = PLAYBOOK_PROMPT,
) -> int:
    """
    Run daily distillation: episodes → playbook entries.
    Returns number of playbook entries created/updated.
    """
    logger.info("starting daily distillation")
    episodes = await db.get_recent_episodes(days=1)
    if not episodes:
        logger.info("no episodes today, skipping distillation")
        return 0

    existing = await db.get_all_playbooks()
    logger.debug(
        "distillation input: %d episodes, %d existing playbooks",
        len(episodes), len(existing),
    )

    episodes_text = "\n\n".join(
        f"Episode #{e['id']} ({e['started_at']} to {e['ended_at']}):\n{e['summary']}"
        for e in episodes
    )

    playbooks_text = (
        "\n\n".join(
            f"- **{p['name']}** (confidence: {p['confidence']}, maturity: {p.get('maturity', 'nascent')})\n"
            f"  Context: {p['context']}\n"
            f"  Action: {p['action']}\n"
            f"  Evidence: {p['evidence']}"
            for p in existing
        )
        if existing
        else "(none yet — this is the first distillation)"
    )

    try:
        prompt = prompt_template.format(
            playbooks=playbooks_text, episodes=episodes_text,
        )
        resp = await client.acomplete(prompt, MODEL_DEEP)
        logger.debug("opus response: %d chars", len(resp.text))

        cost_usd = resp.cost_usd or 0
        await db.record_usage(
            model=MODEL_DEEP,
            layer="distill",
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            cost_usd=cost_usd,
        )
        await db.insert_pipeline_log(
            stage="distill",
            prompt=prompt,
            response=resp.text,
            model=MODEL_DEEP,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            cost_usd=cost_usd,
        )
        logger.debug("recorded usage: model=%s cost=$%.6f", MODEL_DEEP, cost_usd)

        entries = parse_llm_json(resp.text)
        logger.debug("opus returned %d playbook entries", len(entries))

        count = 0
        for entry in entries:
            # Store the rich 情境-行動對 as JSON in the action field
            rich_action = json.dumps(
                {
                    "intuition": entry.get("intuition", ""),
                    "action": entry.get("action", ""),
                    "why": entry.get("why", ""),
                    "counterexample": entry.get("counterexample"),
                },
                ensure_ascii=False,
            )
            await db.upsert_playbook(
                name=entry["name"],
                context=entry.get("context", ""),
                action=rich_action,
                confidence=entry.get("confidence", 0.5),
                evidence=json.dumps(entry.get("evidence", [])),
                maturity=entry.get("maturity", "nascent"),
            )
            # Write memory file
            playbooks_after = await db.get_all_playbooks()
            pb = next((p for p in playbooks_after if p["name"] == entry["name"]), None)
            if pb:
                write_playbook(pb)
            count += 1

        logger.info(
            "Daily distillation: %d entries from %d episodes",
            count,
            len(episodes),
        )
        return count

    except Exception:
        logger.exception("Daily distillation failed")
        return 0
