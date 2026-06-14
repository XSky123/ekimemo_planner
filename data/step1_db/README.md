# Step1 DB

This directory is the canonical Step1 handoff artifact.

User-facing reports remain Chinese. Source facts are stored in Japanese. Schema keys are English.

## Files

- `denko_facts.jsonl`: one canonical row per denko.
- `skill_facts.jsonl`: one canonical skill row per denko.
- `denko_index.json`: lookup index by `denko_id`, pool, wiki no, and name.
- `manifest.json`: source batches, dedupe notes, parser version, metrics, and output paths.
- `validation.json`: deterministic validation result.

## Scope

- Included: `original` 001-163 and `extra` 001-127.
- Excluded from Step1: special/collaboration denko, solver logic, recommendation priors, and observed team cases.

## Current Counts

- `original`: 163 denko rows and 163 skill rows.
- `extra`: 127 denko rows and 127 skill rows.
- Total: 290 denko rows and 290 skill rows.

## Notes

- Batch files under `data/records/` are intermediate/provenance artifacts.
- `original:040` and `original:080` appeared in overlapping historical batches; final DB dedupes them with identical hashes.
- Rebuild with:

```powershell
python pipeline\ingest\build_step1_db.py
```
