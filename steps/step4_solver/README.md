# Step 4: Solver

Status: in progress.

Step3 role profiles are available and schema-validated. Read `TODO.md` and the request schema before touching broad Step1 data.

Goal:

- Implement constrained team search.
- Apply hard constraints before scoring.
- Project effects into the requested scene.
- Output Pareto results rather than one global best.

## First Increment

1. Stabilize `schemas/solver_request.schema.json` and add an explainable result schema.
2. Use `data/role_profiles/role_profiles.jsonl` as the only candidate-fact input.
3. Validate component applicability to the fixed main denko and requested context before scoring.
4. Keep scene contribution dimensions separate and return bounded Pareto alternatives.
5. Add fixed regression cases before generating the first Chinese recommendation report.

## Current Artifacts

- `schemas/solver_request.schema.json` and `schemas/solver_result.schema.json`
- `pipeline/solver/solve_team.py`
- `pipeline/solver/test_solver_regressions.py`
- `pipeline/solver/run_step4_checks.py`
- `data/solver_examples/`

The solver is still an internal candidate generator. It uses the Step3 source
profile hash in its cache key and emits per-component inactive/pending reasons;
do not convert its output into a final recommendation report before the audit
script and the requested scene context both pass.

Observed teams and user account exports remain optional calibration evidence under `data/observed_cases/`; they do not block this deterministic first increment.
