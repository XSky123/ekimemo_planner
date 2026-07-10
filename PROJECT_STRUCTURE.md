# Project Structure

Use this file to avoid confusing legacy/prototype files with the new step-based pipeline.

## Active Top Level

- `README.md`: minimal project entrypoint.
- `ROADMAP.md`: current step and step overview.
- `PROJECT_STRUCTURE.md`: directory responsibilities.
- `.editorconfig`: repository text defaults; keep UTF-8 and LF line endings.
- `docs/solver_spec.md`: long-form generalized solver/agent design; read only for solver/scene-model work.
- `archive/`: protected legacy snapshots and closed-phase evidence. Do not use it as current facts.
- `steps/`: canonical execution folders. Prefer these for handoff.
- `docs/`: shared reference docs used by steps.
- `schemas/`: JSON schemas for structured records.
- `data/`: pipeline inputs/outputs and generated records. `data/step1_db/` is the canonical Step 1 DB handoff; batch files under `data/records/` are provenance/intermediate artifacts.
- `pipeline/`: ingestion, normalization, backfill, audit, and report generation scripts.
- `cache/`: tracked project rules plus ignored runtime web/prototype caches.

## Data Boundaries

- Final Step 1 output goes under `data/step1_db/`.
- `data/records/`: retained batch source records used to rebuild Step1. Numbered filenames are intentional provenance and must not be merged without migrating patch/replay scripts.
- `data/manual_fills/`: accepted semantic patches used when replaying ingestion.
- `data/review_queue/`: only active unresolved review batches; closed queues are archived.
- `data/audits/`: stable current audit outputs.
- `data/reports/`: formal human-facing reports only. Temporary batch reports go to ignored `tmp/review_runs/`.
- `data/raw_pages/`: ignored local fetch cache used by parsers and a few report supplements.
- `data/prototype_db/`: structured prototype/route lookup data.
- `cache/project_rules.json`: the only tracked active cache/config file.
- `.vscode/settings.json` may exist locally for terminal/editor defaults, but `.vscode/` is ignored and not a handoff artifact.

## Step-Based Reading

When working on a step, read only:

1. `cache/project_rules.json`
2. `ROADMAP.md`
3. `steps/<current_step>/README.md`
4. `steps/<current_step>/TODO.md` or manifest if present
5. Directly referenced docs/schemas/data

Open `docs/solver_spec.md` only for Step3-5 design work.
