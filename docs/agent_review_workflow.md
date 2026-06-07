# Agent Review Workflow

This project uses small, bounded agents for ingestion review. Agents must be reusable by future AI runs and must not depend on chat memory.

## Agents

### Batch Review Expert

Prompt file: `.agents/batch_review_expert.md`

Use this after each 20-30 denko batch, or when a batch report looks suspicious.

Responsibilities:

- Read the batch HTML report first.
- Compare only matching JSONL rows.
- Learn from `data/observed_cases/`.
- Find semantic failures in target, filter, trigger, labels, Lv30/Lv50, VU, and component values.
- Output Chinese findings, not code.

It is read-only.

### Manual Semantic Fill Agent

Prompt file: `.agents/manual_semantic_fill_agent.md`

Use this when one denko/page is too ambiguous for deterministic parsing but the report shows exactly what needs correction.

Responsibilities:

- Inspect one denko or one component at a time.
- Use the HTML report as the visible baseline.
- Produce JSONL patch proposals under `data/manual_fills/`.
- Keep Japanese evidence and English keys.
- Never directly edit fact records.

## Learned Review Priorities

From the `original_120_163` and `original_080_119` review loops, the user cares most about:

- component labels matching `(1)`, `(2)`, `(3)`,
- Lv30/Lv50 completeness for non-VU effects,
- explicit VU-only metadata,
- separating target receiver from activation/formation/opponent conditions,
- preserving probability, duration, cooldown, and level-specific values,
- representing access direction, station ownership, link events, battery use, time, weather, weekday, mileage, and relative position,
- not force-filling weird cases when a manual or LLM snippet review is safer.

## When To Use Which Agent

Use Batch Review Expert when:

- a new batch report is generated,
- parser version changed,
- many records have new review reasons,
- the controller needs a second pass before continuing.

Use Manual Semantic Fill Agent when:

- the report points to a concrete ambiguous denko/component,
- the parser has already extracted raw rows,
- a source-backed patch is possible from a small Japanese snippet,
- a one-off correction is needed before a general parser rule exists.

## Manual Patch Flow

1. Run ingestion and generate the HTML report.
2. Batch Review Expert identifies manual fill candidates.
3. Manual Semantic Fill Agent writes `data/manual_fills/<batch>_semantic_patches.jsonl`.
4. A controller or worker reviews the patches.
5. Accepted patches may become:
   - manual overrides, if one-off,
   - parser rules, if repeated,
   - review evidence, if still uncertain.

Manual patches are proposals. They do not override detail-page facts by themselves.

## Context Budget

Do not send agents entire wiki pages or whole databases.

Good context:

- one HTML report path,
- one batch skill JSONL path,
- one denko id,
- one relevant row snippet,
- observed cases for the same pattern.

Bad context:

- all raw wiki pages,
- all records across all batches,
- unbounded conversation history.
