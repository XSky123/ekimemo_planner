# Step1 Ingestion Rules

Step1 is complete but remains incrementally maintainable when new supported denko are added. Current pools are Original, Extra, Another, IKS.gear, EKICO and アワメモ限定; event/collaboration pools remain excluded.

## Authority And Language

- Detail wiki pages are fact authority.
- List pages provide ids, names, detail URLs, type, attribute and VU discovery.
- Beginner recommendation pages are priors/QA only.
- Observed teams and screenshots are case/calibration evidence, never correctness labels.
- Chinese is used for human-facing output; Japanese source text is stored unchanged; structured keys are English.

## Active Paths

- Raw page cache: `data/raw_pages/` (ignored, local, reused by hash/source freshness).
- Batch rebuild inputs: `data/records/`.
- Accepted manual patches: `data/manual_fills/`.
- Active unresolved queue: `data/review_queue/`.
- Transient indexes, batch reports, controller state and prompts: `tmp/review_runs/`.
- Canonical output: `data/step1_db/`.
- Stable audits: `data/audits/`.
- Closed Step1 review evidence: `archive/step1_ingestion_2026-07-11/`.

Historical review queues are read through `parse.review_queue_path()`, which checks the active queue before the archive.

## Controller Workflow

1. Read list/index and target records; do not load the whole DB into an LLM.
2. Reuse a cached page when its source/hash is still valid.
3. Expand `rowspan` and `colspan` into a table matrix before column mapping.
4. Parse list and detail pages deterministically.
5. Split one skill into independent `skill_components` for default, additional and supplemental effects.
6. Run normalization/backfills and rebuild `data/step1_db/`.
7. Run deterministic validation and report audits.
8. Escalate only the smallest ambiguous Japanese snippet to semantic review.

Default ingestion batches are 20-30 denko. Batch filenames in `data/records/` are intentional because accepted patch files and replay commands use those stems. Active batch ranges must not overlap; when a stem changes, rename its manual patch and archived review queue together.

## Parser Failure Rules

- A detected `(1)/(2)/(3)` label count or order mismatch is blocking.
- Label-specific values and probabilities must not inherit a sibling label's cells.
- Distinguish trigger actor, access direction and effect recipient.
- Distinguish own-team attribute constraints from opponent attributes.
- Preserve exclusions and negative clauses; do not emit them as positive effects.
- VU-only components require explicit availability.
- Wiki `x` or `?` values are `unrecorded`; never collapse their known lower bound to zero.
- Formula values such as `4 x n` require materialized bounds from headers such as `n=0-6`.
- Use screenshots only when the visual merged-cell layout cannot be established from the table matrix.

## Review And Patches

- Repeated deterministic failures should produce a parser/backfill rule before LLM review.
- Accepted manual corrections must keep source/reason metadata and a stable patch id.
- Stable report corrections that change facts or semantics must be backfilled into batch records/Step1 DB.
- DB backfill locks must survive parser reruns.
- Confirmed mutually exclusive branches must be stored as separate components. `build_step1_db.py` reapplies the special-pool semantic backfill before merging records, so a re-fetch cannot restore an unsplit parse.
- Closed review queues are historical evidence, not current unresolved work.

## Rebuild

```powershell
python pipeline\ingest\build_step1_db.py
python pipeline\analysis\build_step2_reports.py
```

Acceptance: `307 denko / 307 skills`, all pool counts exact, Step1 `issue_count = 0`, Step2 semantic audit `total_issue_rows = 0`, UTF-8/LF smoke checks clean.
