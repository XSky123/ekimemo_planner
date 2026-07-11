# Step4 Active TODO

## First Deliverable

Build a deterministic, on-demand constrained team solver from Step3 role profiles.

1. [done] Define `solver_request` and an explainable result shape.
2. [done] Project direct component effects into a requested scene without mixing unrelated channels.
3. [done] Enforce currently structured target/attribute/type/environment/opponent conditions before counting contribution; unknown structured restrictions remain `pending_context`.
4. [done] Enumerate a bounded candidate pool and return Pareto teams, not a single global score.
5. [done] Emit inactive-component and unsatisfied-condition reasons for every returned result.
6. [done] Add fixed solver regressions for self-only exclusion, all-attribute breakage, probability expectation, probability ranges, station/accessor conditions and defense-not-capture leakage.
7. [done] Add explicit weather, temperature band/gap, weekday, month/season, time-window, station/accessor attribute and link-time context adapters. Unknown values remain pending rather than assumed.
8. [next] Add the remaining formation/type/position, invalidation scope, opponent diversity and condition-dependent branch adapters; prioritize `data/audits/step4_solver_audit.json` coverage groups.
9. [next] Ingest user ownership/team screenshots resumably as calibration evidence; use them for ranking calibration and explanation checks only, never as fact overrides.
10. [next] Add pair/synergy evaluation for skill-effect modifiers, cooldown/probability operators, equipment/film effects and explicit position-sensitive interactions.
11. [next] Add a request UI/API after solver regressions remain stable across real user scenarios.

## Current Progress

- Request/result schemas, component-level active/inactive/pending reasons, bounded Pareto search, and deterministic example requests exist.
- `pipeline/solver/test_solver_regressions.py` covers self-only exclusion, all-attribute formation, exact probability expectation, range-probability non-averaging, channel isolation, accessor/station matching, opponent-count context, temperature bands/gaps and seasonal months.
- `pipeline/solver/run_step4_checks.py` writes `data/audits/step4_solver_audit.json`; run it after any Step1/Step3 semantic change before trusting solver output.
- `data/reports/step4_solver_examples_zh.html` is the current Chinese, source-linked scene explanation artifact; it is rebuilt from fresh solver outputs rather than edited by hand.
- Still pending: high-impact unmodeled constraints, pair/synergy scoring, real user scenario audit and observed-case calibration ingestion.

## Boundary

This first solver is a candidate generator. Final user-facing recommendations must still record source hashes and detail-page review status; no stale cache may be presented as a final answer.
