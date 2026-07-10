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

- Included: `original` 001-165 and `extra` 001-128.
- Excluded from Step1: special/collaboration denko, solver logic, recommendation priors, and observed team cases.

## Current Counts

- `original`: 165 denko rows and 165 skill rows.
- `extra`: 128 denko rows and 128 skill rows.
- Total: 293 denko rows and 293 skill rows.

## Notes

- Batch files under `data/records/` are retained rebuild inputs and provenance. Their numbered names are tied to manual patch/replay tooling.
- Accepted semantic corrections live under `data/manual_fills/` and in locked DB backfills.
- Closed Step1 review queues and final historical audits live under `archive/step1_ingestion_2026-07-11/`.
- `original:040` and `original:080` appeared in overlapping historical batches; final DB dedupes them with identical hashes.
- Rebuild with:

```powershell
python pipeline\ingest\build_step1_db.py
```
