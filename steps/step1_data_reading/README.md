# Step 1: Data Reading

Status: complete.

Read order for this step:

1. `steps/step1_data_reading/README.md`
2. `steps/step1_data_reading/manifest.json`
3. `steps/step1_data_reading/checklist.md`
4. `docs/controller_ingestion.md`
5. `docs/data_reading_execution_rules.md`
6. `docs/skill_component_model.md`
7. Relevant schemas in `schemas/`

Goal:

- Read and cache Original + Extra wiki data.
- Parse list pages, detail pages, and recommendation priors.
- Generate cleaned JSON/JSONL records and review queue.
- Do not run solver.

Important rules:

- Use `denko_id`, not name, as stable key.
- Expand `rowspan` and `colspan` before mapping table columns.
- Detail pages also require table matrix parsing.
- Use screenshot evidence when visual layout is needed.
- Recommendation pages are prior-only.
- Skill reverse lookup pages are candidate/discovery sources only; use detail pages to confirm values, duration, cooldown, probability, and exact conditions.
- Do not flatten one skill into one label; split team-building effects into `skill_components`.
- Skill/value checkpoint levels are `1/15/30/50/60/70/80/92/96/100`; default practical comparison focuses on `30` and `50`, and `92/96/100` are VU-only.
- Observed teams/screenshots are case/calibration-only.
- Use controller-first ingestion: scripts/cache/parsers first, LLM only for minimal ambiguous snippets or repeated parser failures.
- LLM only receives the smallest ambiguous Japanese snippet.
- Stop after every 20-30 parsed denko records for periodic key/schema review.
- Default human-facing reports are exported as HTML under `data/reports/`.
- Current detail/list parser entrypoint: `pipeline/ingest/parse.py`.

Outputs:

- `data/step1_db/denko_facts.jsonl`
- `data/step1_db/skill_facts.jsonl`
- `data/step1_db/denko_index.json`
- `data/step1_db/manifest.json`
- `data/step1_db/validation.json`
- Batch/intermediate records remain under `data/records/`.
- Batch/intermediate indexes remain under `data/indexes/`.
- Batch/intermediate review queues remain under `data/review_queue/`.
- `data/records/recommendation_priors.jsonl`
- `data/records/reverse_skill_lookup_candidates.jsonl`
- `data/records/observed_team_cases.jsonl`
- `data/reports/*.html`
