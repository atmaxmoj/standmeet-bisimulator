"""Playbook distillation prompt template (formerly DISTILL_PROMPT)."""

PLAYBOOK_PROMPT = """\
You are a master craftsman studying an apprentice's work journal to understand \
how they think, decide, and act — not what they did, but how and why.

Your goal: distill recurring behavioral patterns into Playbook entries. \
A Playbook entry is a 情境-行動對 (situation-action pair) — not a description \
of what someone is, but a recipe for reproducing how they behave in a specific context.

## Existing Playbook
{playbooks}

## Today's episodes
{episodes}

## How to analyze

**Phase 1 — Pattern detection**
Scan all episodes. Look for:
- Recurring sequences: same type of situation → same approach (≥2 occurrences)
- Turning points: moments of correction, choice, or hesitation that reveal preference
- Avoidance patterns: tools/features/steps available but consistently NOT used — \
"never" reveals more than "always"
- Pressure-revealed behavior: what they do under time pressure vs normal. \
Habits dropped under pressure = learned discipline. Habits kept = internalized.

**Phase 2 — Cross-validation**
For each candidate pattern, ask:
- Does this appear across different apps/contexts? (cross-domain = high confidence)
- Are there counter-examples this week? If so, what was different? (boundary conditions)
- Does this confirm, contradict, or extend an existing Playbook entry?

**Phase 3 — Output**
For each pattern, produce a Playbook entry in 情境-行動對 format:

Output valid JSON array:
[
  {{
    "name": "kebab-case-name",
    "context": "The specific situation/trigger (be precise: WHEN does this apply?)",
    "intuition": "Their first/instinctive reaction in this context",
    "action": "What they consistently do (the reproducible sequence)",
    "why": "Inferred reason — what value or constraint drives this choice",
    "counterexample": "Any episode where they did NOT follow this pattern, and why (null if none)",
    "confidence": 0.0,
    "maturity": "nascent|developing|mature|mastered",
    "evidence": [1, 2, 3]
  }}
]

## Confidence & maturity rules
- confidence: 0.3 = weak signal (2 episodes), 0.6 = clear pattern (3-4), 0.8+ = very consistent (5+)
- nascent: < 3 evidence episodes or confidence < 0.6
- developing: 3-8 evidence, confidence mostly 0.6-0.8
- mature: > 8 evidence, confidence mostly > 0.8
- mastered: mature + has counterexamples with identified boundary conditions + survives pressure

## Rules
- Patterns, not one-offs. Minimum 2 episodes as evidence.
- Update existing entries when you see confirming or contradicting evidence. \
Increment confidence for confirmation, note counterexamples for contradiction.
- Create new entries only for clearly recurring patterns.
- If an episode shows behavior UNDER PRESSURE (marked under_pressure=true), \
compare it to the normal pattern. This is gold — it shows what's truly internalized.
- Look for cross-domain patterns: if someone does the same thing across debugging, \
writing, and communication, that's a value, not just a habit.

Output ONLY the JSON array, nothing else."""

# Backwards compat alias
DISTILL_PROMPT = PLAYBOOK_PROMPT
