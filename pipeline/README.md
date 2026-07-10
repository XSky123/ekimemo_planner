# Pipeline

- `ingest/`: fetch, parse, normalize, backfill, validate and Step1 audit code.
- `analysis/`: Step2 candidate reports, combined report and semantic audit.
- `prototype/`: route/vehicle/station prototype lookup extraction and rendering.

Generated formal artifacts belong under `data/step1_db`, `data/reports`, `data/audits`, or `data/prototype_db`. Transient batch reports and controller state belong under ignored `tmp/review_runs`.

Step3 role-profile code should use a new `pipeline/profiles/` boundary. Solver search belongs in a later `pipeline/solver/` boundary.
