"""Routine composition prompt template."""

ROUTINE_PROMPT = """\
You are studying someone's daily work journal and their known behavioral patterns (Playbook) \
to identify **Routines** — recurring multi-step workflows they follow in specific situations.

A Routine is NOT a single habit (that's a Playbook entry). \
A Routine is a **composed sequence of steps** that this person repeats when a specific \
trigger/situation occurs. Think of it as their personal SOP (standard operating procedure).

## Existing Playbook entries (atomic behaviors)
{playbooks}

## Existing Routines
{routines}

## Today's episodes
{episodes}

## How to analyze

**Phase 1 — Sequence detection**
Look for multi-step sequences that repeat across episodes:
- Same trigger → same sequence of actions (≥2 occurrences across different days)
- Steps that always appear together in a specific order
- "Warm-up" sequences: what someone does before starting a task type

**Phase 2 — Compose from Playbook**
Each Routine should reference existing Playbook entries where applicable. \
The Routine adds the **ordering, branching, and context** that individual entries lack.

**Phase 3 — Output**
Output valid JSON array:
[
  {{
    "name": "kebab-case-name",
    "trigger": "When/what situation triggers this routine",
    "goal": "What this routine achieves",
    "steps": [
      "Step 1 description",
      "Step 2 description",
      "IF condition THEN step 3a ELSE step 3b",
      "Step 4 description"
    ],
    "uses": ["playbook-entry-name-1", "playbook-entry-name-2"],
    "confidence": 0.0,
    "maturity": "nascent|developing|mature"
  }}
]

## Rules
- A Routine must have ≥3 steps (otherwise it's just a Playbook entry)
- A Routine must be observed ≥2 times to be created
- Update existing Routines when you see confirming evidence (bump confidence) \
or variations (update steps to capture the common core)
- `uses` should list Playbook entry names that correspond to steps in this Routine
- Steps can include simple branching: "IF x THEN y ELSE z"
- Keep step descriptions concise — one line each

## Confidence & maturity rules
- confidence: 0.4 = seen twice, 0.6 = clear pattern (3-4 times), 0.8+ = very consistent
- nascent: < 3 observations
- developing: 3-5 observations
- mature: > 5 observations with consistent steps

Output ONLY the JSON array, nothing else."""
