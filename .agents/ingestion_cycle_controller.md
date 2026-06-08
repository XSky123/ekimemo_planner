# Ekimemo Ingestion Cycle Controller

Purpose: orchestrate one ingestion batch through repeated parser runs, review-agent checks, parser fixes, and final human review.

This controller is allowed to run scripts and edit parser/rule files. It should not manually rewrite fact records except through documented manual override flows.

## Inputs

- scope: `pool`, `start`, `end`
- current parser version
- current batch state, usually `data/agent_runs/<batch>_cycle_state.json`
- batch review prompt, usually `data/agent_runs/<batch>_batch_review_agent_prompt.md`

## Loop

1. Run:
   - `python pipeline/ingest/review_cycle_controller.py --start <start> --end <end>`
2. If `next_action` is `spawn_batch_review_expert`, start a Batch Review Expert using `.agents/batch_review_expert.md` and the generated prompt.
3. Classify the review output:
   - deterministic repeated issue -> edit parser/rules, rerun step 1
   - one-off semantic ambiguity -> start Manual Semantic Fill Agent
   - screenshot/layout uncertainty -> stop and ask for source confirmation
   - report-only issue -> edit report rendering, rerun step 1
4. After parser edits, run py_compile and rerun the same batch.
5. Continue until no blocking parser health item remains or the remaining issues are explicitly manual/human review candidates.
6. Commit only after the generated records, review queue, report, observed cases, and parser changes agree.

## Stop Conditions

Stop for human final review when:

- `next_action` is `human_final_review`, or
- remaining blocking items are documented one-off manual candidates, or
- the same ambiguous source snippet appears twice without a deterministic rule.

Do not stop merely because the script succeeded. Script success only means the pipeline ran, not that the semantic parse is good.

## High-Priority Health Rules

- `(1)` or a `_1` primary effect parsed as VU-only is suspicious. In most cases it means the base effect and VU addition were misaligned.
- Labels detected in raw text but absent, reordered, or collapsed in components are suspicious.
- Non-VU components missing Lv30 or Lv50 are suspicious.
- Japanese effect words must match `effect_kind`; for example `経験値` or `スコア獲得` should not become DEF/ATK components.
- Opponent/formation/time/weather/weekday/link/access-direction conditions are conditions or filters, not automatically the effect target.
- Merged-cell artifacts can move attributes after the sentence; do not force-fill if the blank mapping is uncertain.

## Output

Each loop should leave:

- updated `data/agent_runs/<batch>_cycle_state.json`
- updated batch HTML report
- any parser/rule changes
- observed-case notes for new reusable lessons
- a concise Chinese handoff summary
