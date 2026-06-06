# Step 1 Execution Checklist

Before fetching:

- `cache/project_rules.json` is readable.
- `ROADMAP.md` says current step is `step1_data_reading`.
- `steps/step1_data_reading/manifest.json` is readable.
- `data/ingestion_manifest.json` is readable.
- JSON schemas in `schemas/` are readable.
- `data/review_evidence/screenshots/` exists.

Parser requirements:

- Use HTML DOM parsing.
- Expand `rowspan` and `colspan` into a table matrix.
- Skip repeated header rows.
- Use `denko_id`, not name, as stable key.
- Store Japanese source text as Japanese.
- Use English keys.
- Recommendation pages are `recommendation_prior` only.
- Observed teams/screenshots are `observed_team_case` only.
- Ambiguous fields go to `review_queue`.
- Use screenshots when layout cannot be proven from HTML/text.
- Parser/agent may add optional keys when the page proves current dimensions are insufficient, but must record `change_reason` and evidence.
- After every 30 denko records, stop and review whether keys/schema/review reasons are still adequate.
- Human-readable reports must be exported as HTML under `data/reports/`.

Do not:

- Do not run solver.
- Do not import Excel.
- Do not parse raw rendered text lines as table rows.
- Do not overwrite detail-page facts with recommendation priors.
- Do not treat legacy `cache/04_solver_results` as Step 1 output.
- Do not silently change required schema fields without review.

Ready state:

- `prepared = true`
- `fetch_started = false`
- `parse_started = false`
- `complete = false`
