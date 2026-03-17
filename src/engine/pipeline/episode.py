"""Task-level: Haiku analyzes a time window, identifies tasks, and creates episodes."""

import base64
import json
import logging
from pathlib import Path

from engine.config import MODEL_FAST
from engine.db import DB
from engine.domain.prompts.episode import EPISODE_PROMPT  # noqa: F401
from engine.llm import LLMClient, LLMResponse
from engine.pipeline.collector import Frame
from engine.pipeline.validate import strip_fence

logger = logging.getLogger(__name__)


# ── Reusable building blocks ──


def build_context(frames: list[Frame]) -> str:
    """Build the text context from a list of frames (capture + audio + os_event)."""
    lines = []
    for f in frames:
        text = f.text[:300].replace("\n", " ")
        source_tag = f"[{f.source}]" if f.source != "screenpipe" else ""
        lines.append(f"[{f.timestamp}] {f.app_name}/{f.window_name}{source_tag}: {text}")
    return "\n".join(lines)


def build_context_from_dicts(
    frames: list[dict],
    audio: list[dict] | None = None,
    os_events: list[dict] | None = None,
) -> str:
    """Build context from raw API dicts (for experiments/tests)."""
    lines = []
    for f in frames:
        text = f["text"][:300].replace("\n", " ")
        lines.append(f"[{f['timestamp']}] {f['app_name']}/{f['window_name']}[capture]: {text}")
    for a in (audio or []):
        lines.append(f"[{a['timestamp']}] [audio]: {a['text'][:300]}")
    for e in (os_events or []):
        lines.append(f"[{e['timestamp']}] [os_event/{e['event_type']}]: {e['data'][:300]}")
    lines.sort()
    return "\n".join(lines)


def parse_llm_json(text: str) -> list[dict]:
    """Parse JSON from LLM response, handling markdown code fences."""
    result = json.loads(strip_fence(text))
    if not isinstance(result, list):
        result = [result]
    return result


async def extract_episodes(
    client: LLMClient,
    context: str,
    prompt: str = EPISODE_PROMPT,
    model: str = MODEL_FAST,
) -> tuple[list[dict], LLMResponse]:
    """Pure LLM call: context + prompt → parsed episodes + response metadata.

    No DB writes. Reusable for experiments with different prompts.
    """
    prompt_text = prompt.format(context=context)
    resp = await client.acomplete(prompt_text, model)
    tasks = parse_llm_json(resp.text)
    return tasks, resp


# ── Pipeline integration (with DB writes) ──


def _sample_images(
    frames: list[Frame],
    frames_base_dir: str,
    max_images: int = 5,
) -> list[tuple[int, str, bytes]]:
    """Sample up to max_images from the window, evenly spaced."""
    frames_with_images = [f for f in frames if f.image_path]
    if not frames_with_images:
        return []
    step = max(1, len(frames_with_images) // max_images)
    sampled = frames_with_images[::step][:max_images]

    result = []
    for f in sampled:
        path = Path(frames_base_dir) / f.image_path
        if not path.exists():
            continue
        image_bytes = path.read_bytes()
        b64 = base64.standard_b64encode(image_bytes).decode("ascii")
        result.append((f.id, "image/webp", b64))

    logger.debug(
        "sampled %d images from %d frames with images (of %d total)",
        len(result), len(frames_with_images), len(frames),
    )
    return result


async def process_window(
    client: LLMClient,
    db: DB,
    frames: list[Frame],
    frames_base_dir: str = "",
    prompt: str = EPISODE_PROMPT,
) -> list[int]:
    """Full pipeline: frames → context → LLM → parse → save to DB.

    Returns list of created episode IDs.
    """
    if not frames:
        logger.debug("process_window called with empty frames, skipping")
        return []

    logger.debug(
        "process_window: %d frames, time range [%s, %s]",
        len(frames), frames[0].timestamp, frames[-1].timestamp,
    )

    context = build_context(frames)
    logger.debug("built context: %d lines, %d chars", context.count("\n") + 1, len(context))

    try:
        tasks, resp = await extract_episodes(client, context, prompt=prompt)
        logger.debug("haiku identified %d tasks in window", len(tasks))

        cost_usd = resp.cost_usd or 0
        await db.record_usage(
            model=MODEL_FAST, layer="episode",
            input_tokens=resp.input_tokens, output_tokens=resp.output_tokens,
            cost_usd=cost_usd,
        )
        prompt_text = prompt.format(context=context)
        await db.insert_pipeline_log(
            stage="episode", prompt=prompt_text, response=resp.text,
            model=MODEL_FAST, input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens, cost_usd=cost_usd,
        )

        frame_id_min = min(f.id for f in frames)
        frame_id_max = max(f.id for f in frames)
        sources = set(f.source for f in frames)
        frame_source = ",".join(sorted(sources))

        episode_ids = []
        for task in tasks:
            summary = json.dumps(
                {
                    "summary": task.get("summary", ""),
                    "method": task.get("method", ""),
                    "turning_points": task.get("turning_points", []),
                    "avoidance": task.get("avoidance", []),
                    "under_pressure": task.get("under_pressure", False),
                },
                ensure_ascii=False,
            )
            episode_id = await db.insert_episode(
                summary=summary,
                app_names=json.dumps(task.get("apps", [])),
                frame_count=len(frames),
                started_at=task.get("started_at", frames[0].timestamp),
                ended_at=task.get("ended_at", frames[-1].timestamp),
                frame_id_min=frame_id_min,
                frame_id_max=frame_id_max,
                frame_source=frame_source,
            )
            episode_ids.append(episode_id)
            logger.info("Created episode #%d: %s", episode_id, task.get("summary", "")[:80])

        return episode_ids

    except Exception:
        logger.exception("Failed to process window (%d frames)", len(frames))
        return []
