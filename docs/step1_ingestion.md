# Step 1: Ingestion Prep

Goal: prepare records that another AI or program can resume from without conversation context.

Before execution, read `docs/data_reading_execution_rules.md`.

Minimum outputs:

- `data/records/denko_facts.jsonl`
- `data/records/skill_facts.jsonl`
- `data/records/recommendation_priors.jsonl`
- `data/records/observed_team_cases.jsonl`
- `data/indexes/denko_index.json`
- `data/review_queue/review_queue.jsonl`

ID mapping:

- The Original and Extra wiki list pages are the canonical source for denko id to detail page mapping.
- Original ids use numeric `No.` values and should normalize to `original:000`, `original:001`, etc.
- Extra ids use `EXxx` values and should normalize to `extra:001`, `extra:035`, etc.
- Store both the source value as `wiki_no` and the normalized value as `denko_id`.
- The linked name cell is the canonical first-pass `detail_url`.
- List-page row fields to capture on first pass: `wiki_no`, linked `name`, `detail_url`, `type`, `attribute`, `color`, `skill_name`, `vu_marker`, `remarks`.
- Detail pages can confirm or enrich facts, but should not erase the original list-page id mapping unless the page is clearly wrong and a manual override records why.

Minimum metadata on every record:

- `source_url`
- `source_authority`
- `content_hash`
- `parser_version`
- `parsed_at`
- `confidence`
- `needs_review`
- `review_reasons`

Parsing principle:

- Deterministic parser first.
- LLM only receives the smallest ambiguous Japanese snippet.
- Recommendation pages never overwrite detail-page facts.
- Observed teams/screenshots never become skill facts by themselves.
