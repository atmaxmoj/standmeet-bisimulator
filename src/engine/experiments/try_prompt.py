#!/usr/bin/env python3
"""Try prompt experiment — runs INSIDE Docker container.

Usage: npm run experiment [-- <frame_limit>]

Each LLM call saves its result immediately to /data/experiment_results/.
No dependency on stdout capture or bash timeout.
"""

import asyncio
import json
import sys
from pathlib import Path

from engine.config import Settings, MODEL_FAST
from engine.db import DB
from engine.llm import create_client
from engine.pipeline.episode import (
    EPISODE_PROMPT,
    build_context_from_dicts,
    extract_episodes,
)

FRAME_LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 50
EVENT_LIMIT = min(FRAME_LIMIT, 30)
RESULTS_DIR = Path("/data/experiment_results")

DEEP_EPISODE_PROMPT = """\
You are a behavioral psychologist studying someone's work by observing their screen activity, \
audio, and system events. You are NOT just summarizing what happened — you are inferring \
HOW they think, WHY they make decisions, and WHAT their mental model reveals.

Analyze this activity window and identify the distinct tasks performed.

Data sources:
- **[capture]** — screen captures with OCR text
- **[audio]** — microphone transcriptions
- **[os_event]** — shell commands and browser URLs

For each task, analyze at THREE levels:

### Level 1: Observable behavior (what happened)
What did they do? What tools, what sequence, what outcome?

### Level 2: Methodology (how they approach problems)
Not "they ran tests" but "their methodology is test-verify-commit — they treat each commit \
as a verified checkpoint, not a save point." Look for:
- Problem-solving strategy: do they debug top-down or bottom-up? guess-and-check or systematic?
- Information gathering: do they read docs, search, ask AI, or read source code first?
- Risk management: do they create safety nets (branches, backups) before risky changes?
- Iteration style: big rewrites or incremental small changes?

### Level 3: Abduction (infer their mental state and reasoning)
From observable behavior, infer the UNOBSERVABLE:
- **Intent**: what were they trying to achieve at each decision point?
- **Mental model**: what does their behavior reveal about how they understand the system?
- **Confidence level**: were they exploring (uncertain) or executing (confident)?
- **Emotional state**: frustrated (rapid switches, deletions), focused (long deep sessions), \
  or distracted (many context switches)?
- **Decision reasoning**: when they chose X over Y, WHY? What constraint or value drove that?

Activity log:
{context}

Output valid JSON array (one object per task):
[
  {{
    "summary": "2-4 sentences: what they did, tools, key decisions, outcome",
    "methodology": "How they approached this task — their strategy, not just their steps",
    "abduction": {{
      "intent": "What they were trying to achieve and why NOW",
      "mental_model": "What their behavior reveals about how they think about this system/problem",
      "confidence": "exploring|executing|mixed — with reasoning",
      "emotional_state": "focused|frustrated|distracted|rushed — with evidence",
      "key_decisions": ["Decision X over Y because Z (inferred)"]
    }},
    "turning_points": ["moments of correction, choice, hesitation — with inferred reasoning"],
    "avoidance": ["tools/features available but not used — with inferred WHY"],
    "under_pressure": false,
    "apps": ["App1", "App2"],
    "started_at": "...",
    "ended_at": "..."
  }}
]

Remember: you're not a journalist reporting facts. You're a psychologist building a model \
of how this person's mind works. Every action is a data point about their cognition.

Output ONLY the JSON array, nothing else."""

PROMPTS = {
    "current": EPISODE_PROMPT,
    "deep": DEEP_EPISODE_PROMPT,
}


def _save(name: str, data: dict):
    """Save result immediately after each LLM call."""
    path = RESULTS_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"  saved → {path}")


async def main():
    settings = Settings()
    db = DB(settings.db_path)
    await db.connect()

    llm = create_client(
        api_key=settings.anthropic_api_key,
        auth_token=settings.claude_code_oauth_token,
        openai_api_key=settings.openai_api_key,
        openai_base_url=settings.openai_base_url,
    )

    # Extract
    frames, _ = await db.get_frames(limit=FRAME_LIMIT)
    audio, _ = await db.get_audio_frames(limit=EVENT_LIMIT)
    os_events, _ = await db.get_os_events(limit=EVENT_LIMIT)

    if not frames:
        print("ERROR: No frames in DB")
        return

    # Build
    context = build_context_from_dicts(frames, audio, os_events)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    _save("context", {
        "frame_count": len(frames),
        "audio_count": len(audio),
        "event_count": len(os_events),
        "context_chars": len(context),
    })
    print(f"Input: {len(frames)} frames, {len(audio)} audio, {len(os_events)} events")
    print(f"Context: {len(context)} chars\n")

    # Infer + Parse — each prompt independently, save immediately
    for name, prompt in PROMPTS.items():
        print(f"Running {name} prompt...")
        try:
            episodes, resp = await extract_episodes(llm, context, prompt=prompt, model=MODEL_FAST)
            _save(name, {
                "episodes": episodes,
                "episode_count": len(episodes),
                "input_tokens": resp.input_tokens,
                "output_tokens": resp.output_tokens,
            })
            print(f"  → {len(episodes)} episodes, {resp.output_tokens} tokens out\n")
        except Exception as e:
            _save(name, {"error": str(e), "episodes": []})
            print(f"  → ERROR: {e}\n")

    await db.close()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(main())
