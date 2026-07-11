# Step 6: Calibration And Maintenance

Status: ready for observed-case attachments.

Observed teams, screenshots, and user exports are calibration evidence only.
They never overwrite wiki-detail facts or Step1 records.

## First Intake

1. Place the supplied ZIP under `data/observed_cases/`.
2. Run `python pipeline/calibration/ingest_observed_cases.py`.
3. Read `data/observed_cases/manifest.json` and only targeted rows from `ingest_queue.jsonl`.
4. Parse/OCR one queue item at a time; record confidence, source, and human correction.
5. Compare cases against solver results as calibration evidence, then add a regression only when the wiki-detail fact supports the conclusion.
