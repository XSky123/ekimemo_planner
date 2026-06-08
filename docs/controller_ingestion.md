# Controller-First Ingestion

Purpose: ingest hundreds of denko records without spending model tokens on pages that deterministic scripts can parse.

The controller is an orchestration layer. It should run scripts, cache, classify failures, and produce review reports. It should not ask an LLM to read complete wiki pages or the whole DB.

## Default Flow

1. Read `cache/project_rules.json`, step manifest, and indexes.
2. Reuse cached raw pages when `content_hash` is unchanged.
3. Fetch only missing, stale, or explicitly refreshed pages.
4. Run deterministic parsers:
   - DOM table matrix with `rowspan`/`colspan`.
   - detail-page skill extraction.
   - `skill_components` split.
   - key-level AP/HP/Exp extraction.
5. Write records, indexes, review queue, and HTML reports.
6. Classify every record into one of:
   - `parsed_ok`: sufficient confidence, no blocking issue.
   - `needs_parser_rule`: repeated deterministic parse failure that can be fixed in code.
   - `needs_llm_snippet`: small ambiguous Japanese snippet needs semantic split.
   - `needs_manual_review`: conflict, screenshot-needed, or high-impact uncertainty.
7. After each 20-30 denko batch, generate a periodic review report before continuing.

Default batch size is `30`. Use `20` when a new template family or many low-confidence records appear.

## LLM Budget Rules

LLM/model calls are allowed only for:

- Small Japanese snippets that deterministic parsing could not classify.
- Unknown detail-page templates after table extraction succeeds but semantics are unclear.
- Component split decisions where multiple effects are mixed in prose.
- Source conflicts that need a human-readable explanation.
- Periodic review narrative when script metrics alone are not enough.

LLM/model calls are forbidden for:

- Full wiki pages.
- Full JSONL files or the full DB.
- Records whose `content_hash` is unchanged and confidence is sufficient.
- Repeating known parser failures before trying a code rule.

## Auto-Fix Policy

The controller may automatically patch parser rules when:

- The same failure pattern appears repeatedly in the batch.
- The fix is deterministic and source-backed.
- The fix does not overwrite Japanese source facts.

Every auto-fix must record:

- `change_reason`
- affected parser/version
- source URL or sample record
- before/after behavior
- whether it affects solver semantics

If it affects solver semantics, keep affected records in `needs_review`.

## Periodic Review Metrics

Each batch review should include:

- batch range and record count
- parse success rate
- count by `review_reason`
- new or unknown table templates
- new component kinds discovered
- records requiring LLM snippets
- records requiring screenshots/manual review
- schema suggestions and parser changes

Reports are written as HTML under `data/reports/`.

Batch reports should include a fixed 5-slot skill component matrix per denko. Each
slot should expose `kind`, `condition`, `Lv30`, `Lv50`, `probability`, `duration`,
and `CD` so team-building candidates can be compared without reopening several
wiki tables.

## Review Agents

Reusable agent prompts live under `.agents/`.

- Use `.agents/batch_review_expert.md` after a batch report is generated. It is
  read-only and should inspect the HTML report plus matching JSONL rows to find
  target/filter/trigger/label/value problems before the next batch.
- Use `.agents/manual_semantic_fill_agent.md` for one ambiguous denko/component
  at a time. It should write proposed semantic patches to
  `data/manual_fills/<batch>_semantic_patches.jsonl` using
  `schemas/manual_skill_semantic_patch.schema.json`. These patches are proposals,
  not direct fact overrides.
- When the controller accepts a patch without further user intervention, run
  `python pipeline/ingest/apply_manual_semantic_patches.py --batch <batch>`.
  This marks patches as `accepted`, applies them to the matching
  `data/records/<batch>_skill_facts.jsonl`, regenerates the HTML report, and
  refreshes the cycle state.

Agents should learn from `data/observed_cases/`, especially prior manual parser
findings and parser resolution logs, before reviewing the next batch.
