# Data Boundaries

- `step1_db/`: canonical Step1 facts; consumers read this first.
- `records/`: retained non-overlapping batch rebuild inputs. Batch names are tied to patch/replay scripts and are not disposable history.
- `manual_fills/`: stable sourced semantic patches reapplied during rebuilds.
- `review_queue/`: created only for active unresolved ingestion reviews; closed queues live in `archive/`.
- `audits/`: current stable machine-readable audits.
- `reports/`: formal human-facing generated HTML only.
- `prototype_db/`: canonical prototype route/station/vehicle lookup records.
- `observed_cases/`: reserved for future real team/screenshot calibration cases, not parser-review notes.
- `raw_pages/`: ignored reusable fetch cache; local only.

Temporary indexes, batch HTML, controller state and prompts belong under ignored `tmp/review_runs/`.
