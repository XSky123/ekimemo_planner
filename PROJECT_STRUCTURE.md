# Project Structure

Use this file to avoid confusing legacy/prototype files with the new step-based pipeline.

## Top Level

- `README.md`: minimal project entrypoint.
- `ROADMAP.md`: current step and step overview.
- `PROJECT_STRUCTURE.md`: directory responsibilities.
- `ekimemo_team_solver_agent.md`: long-form generalized solver/agent spec. Optional for Step 1 unless a rule is missing from step docs.
- `archive/`: protected snapshots. Do not edit files inside dated archives.
- `steps/`: canonical execution folders. Prefer these for handoff.
- `docs/`: shared reference docs used by steps.
- `schemas/`: JSON schemas for structured records.
- `data/`: new pipeline inputs/outputs and generated records.
- `pipeline/`: future implementation code.
- `cache/`: current project rules plus legacy/prototype caches from the previous agent phase.

## Important Distinction

- New Step 1 output goes under `data/`.
- Old prototype solver/profile cache currently lives under `cache/02_denko_profile`, `cache/03_skill_parsed`, and `cache/04_solver_results`.
- `cache/project_rules.json` and `cache/cache_manifest.json` are still active handoff files.
- Do not treat old prototype cache as confirmed Step 1 output unless a later migration explicitly records it.

## Step-Based Reading

When working on a step, read only:

1. `cache/project_rules.json`
2. `ROADMAP.md`
3. `steps/<current_step>/README.md`
4. `steps/<current_step>/manifest.json` if present
5. Directly referenced docs/schemas/data

Open the long agent spec only when the step docs are insufficient.

