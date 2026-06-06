# Step 1 Periodic Key Review

Cadence: every 30 parsed denko records.

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

Required output:

- HTML report in `data/reports/`.
- Include parsed range, record count, new/missing dimensions, schema suggestions, and blocking issues.

Rule:

- Do not continue to the next batch until the periodic review is recorded.

