# Step 1 Periodic Key Review

Cadence: every 20-30 parsed denko records.

Default batch size: 30.

Use 20 when a new template family or many low-confidence records appear.

Purpose:

- Prevent schema drift from accumulating silently.
- Catch missing dimensions before full-scale ingestion.
- Keep review queue useful instead of noisy.

Review questions:

- Are required fields stable across this batch?
- Did pages repeatedly expose a field not represented in schema?
- Are table evidence fields sufficient to locate the source?
- Are `review_reasons` actionable?
- Are screenshots needed for too many rows?
- Did list-page and detail-page facts conflict?
- Should any debug field become a formal optional key?
- Which records are `parsed_ok`, `needs_parser_rule`, `needs_llm_snippet`, or `needs_manual_review`?
- Are LLM snippet requests small enough, or is the controller accidentally sending too much context?

Required output:

- HTML report in `data/reports/`.
- Include parsed range, record count, new/missing dimensions, schema suggestions, and blocking issues.
- Include parse success rate, review reason counts, component kind counts, LLM snippet count, and parser auto-fix candidates.

Rule:

- Do not continue to the next batch until the periodic review is recorded.
- Do not call an LLM for records that deterministic scripts parsed with sufficient confidence.
