# Step1 Ingestion Archive

Closed historical evidence from the exploratory and batch-review phase.

- `review_queue/`: consumed batch queues retained for replay/report provenance; placeholder review items are closed as `confirmed` after the final audits.
- `audits/`: final Step1 checklist and recommendation-prior audits.
- `parser_review_cases.jsonl`: merged parser-review lessons formerly spread across `data/observed_cases/`; each row keeps `source_file`.

These files are not current facts or active TODOs. Current facts are in `data/step1_db/`; current parser rules are in code and `docs/step1_ingestion_rules.md`.

Historical queue fallback is implemented by `pipeline/ingest/parse.py::review_queue_path`.

On 2026-07-11, active batch stems were normalized to non-overlapping ranges (`original_001_039`, `original_040_079`, `extra_121_126`); matching archived queue stems were renamed with them.
