"""Try prompt — compare different prompt outputs on the same real data.

End-to-end through running Observer API (LLM runs inside Docker).
Skipped by default in npm test.

Run manually:
  cd ~/Develop/projects/bisimulator
  PYTHONPATH=src uv run pytest tests/experiments/test_try_prompt.py -v -s --run-llm

Results saved to tests/experiments/results/
"""

import json
from pathlib import Path

import httpx
import pytest

from engine.pipeline.episode import EPISODE_PROMPT

API = "http://localhost:5001"
RESULTS_DIR = Path(__file__).parent / "results"

FRAME_LIMIT = 50
EVENT_LIMIT = 30

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


def _api_available() -> bool:
    try:
        return httpx.get(f"{API}/engine/status", timeout=3).status_code == 200
    except Exception:
        return False


run_llm = pytest.mark.skipif(
    "not config.getoption('--run-llm', default=False)",
    reason="--run-llm required (connects to real LLM, costs money)",
)


def _try_prompt(prompt: str) -> dict:
    """Call POST /engine/try-prompt on the running Observer API."""
    resp = httpx.post(
        f"{API}/engine/try-prompt",
        json={"prompt": prompt, "frame_limit": FRAME_LIMIT, "event_limit": EVENT_LIMIT},
        timeout=600,
    )
    assert resp.status_code == 200, f"API error: {resp.text}"
    return resp.json()


@run_llm
def test_deep_episode_vs_current():
    """Run both prompts on same data, save results for manual review."""
    if not _api_available():
        pytest.skip("Observer API not running at localhost:5001")

    current = _try_prompt(EPISODE_PROMPT)
    deep = _try_prompt(DEEP_EPISODE_PROMPT)

    assert "error" not in current, f"Current prompt failed: {current}"
    assert "error" not in deep, f"Deep prompt failed: {deep}"

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / "deep_episode_result.json"
    out_path.write_text(json.dumps({
        "context_chars": current["context_chars"],
        "current": current,
        "deep": deep,
    }, indent=2, ensure_ascii=False))

    # Deep episodes should have richer fields
    for ep in deep["episodes"]:
        assert "methodology" in ep, "Deep episode missing methodology"
        assert "abduction" in ep, "Deep episode missing abduction"

    print(f"\n{'='*60}")
    print(f"SAVED: {out_path}")
    print(f"Current: {len(current['episodes'])} episodes, {current['output_tokens']} tokens")
    print(f"Deep:    {len(deep['episodes'])} episodes, {deep['output_tokens']} tokens")
    print(f"{'='*60}")
