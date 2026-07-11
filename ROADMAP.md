# Roadmap

This project is organized by step to reduce AI context cost and handoff errors.

Global read order:

1. `cache/project_rules.json`
2. `ROADMAP.md`
3. Current step README/TODO under `steps/`
4. Current step manifest/rules only
5. Relevant schema and targeted data rows

Read `PROJECT_STRUCTURE.md` only for repository cleanup, ownership questions or unclear paths.

## Current Status

- Current step: `step4_solver`
- Legacy agent: protected in `archive/legacy_agent_2026-06-06/`
- Git repo: active on branch `main`; static reports are published from the minimal `pages` branch.
- Step 1 state: complete and incrementally updated through `original` 001-165, `extra` 001-128, Another AD02-03, IKS0-6, EKICO EC1-4 and アワメモ OR0. Canonical DB lives under `data/step1_db/`.
- Step 2 state: candidate discovery is complete enough to feed role profiles. Reports remain maintainable views, not final team scores.
- Published baseline: Step1 has `307 denko / 307 skills` with `issue_count = 0`; Step2 semantic audit is green. Metric/range/VU cleanup and branch-preserving special-pool backfills are committed and published.
- Step 3 state: comparative scoring rebuilt as `denko_rating.v2`. All `307` characters have seven practical scene scores. Two LLM rounds reviewed each scene's top/bottom 15 eligible candidates (420 review instances), producing Step1 semantic backfills and Step3 normalization fixes. Template recommendations were removed; the report now shows explicit factors and only preserved LLM review text.
- Step 4 state: active with its first deterministic baseline accepted. `pipeline/solver/solve_team.py` has a versioned request/result contract, bounded Pareto search, source-profile hash cache keys, 19 fixed solver regressions, three request fixtures, and a zero-issue audit at `data/audits/step4_solver_audit.json`. Automatic feedback has corrected actor/station conditions (`extra:006`, `extra:107~109`), own-team stat-loss costs (`extra:008`), and the distinction between a holder's own access and any-team-member access. Remaining work is wider scene/context coverage, ownership constraints, observed-case calibration, and expanding the verified local Step5 UI toward saved, source-aware requests.
- Active TODO: `steps/step4_solver/TODO.md`; Step2 decisions are closed in `steps/step2_indexes/CLOSEOUT.md`, and Step3's completed checklist remains at `steps/step3_role_profiles/TODO.md`.

## Steps

### Step 0: Protect Legacy Agent

Path: `steps/step0_protect_legacy/`

Done:

- Archived previous agent spec and rule files.
- Do not edit archived files in place.

### Step 1: Data Reading

Path: `steps/step1_data_reading/`

Goal:

- Read Original, Extra and explicitly supported non-event special-series wiki data.
- Build raw cache, cleaned records, first indexes, and review queue.
- Do not run solver.

Key outputs:

- `data/step1_db/denko_facts.jsonl`
- `data/step1_db/skill_facts.jsonl`
- `data/step1_db/denko_index.json`
- `data/step1_db/manifest.json`
- `data/step1_db/validation.json`
- Rebuild inputs remain under `data/records/` and `data/manual_fills/`.
- Closed review queues/audits are under `archive/step1_ingestion_2026-07-11/`; new unresolved queues use `data/review_queue/`.
- Maintenance rules: `docs/step1_ingestion_rules.md`.

### Step 2: Indexes And Candidate Discovery

Path: `steps/step2_indexes/`

Goal:

- Build searchable indexes from cleaned records.
- Keep recommendation priors and observed team cases separate from facts.
- Generate candidate reports before solver scoring:
  - `data/reports/step2_attack_support_rankings_zh.html`
  - `data/reports/step2_exp_pt_support_rankings_zh.html`
  - `data/reports/step2_defense_support_rankings_zh.html`
  - `data/reports/step2_skill_utility_reports_zh.html`
  - `data/reports/step2_prototype_lookup_zh.html`

Status: complete for candidate discovery; keep semantic audits green when Step1 changes.

### Step 3: Role Profiles

Path: `steps/step3_role_profiles/`

Goal:

- Convert facts into reusable role profiles.
- Do not bind profiles to one fixed main denko.
- Normalize uptime, expected effect, trigger actor/direction, recipient, hard constraints, opportunity cost, and scene tags.
- Do not create a global character score here; record reusable capabilities and costs for later scene projections.

Execution order:

1. Define the schema and generate one deterministic profile per `skill_component`, preserving source DB hash, parser version, locks, raw conditions and confidence.
2. Normalize effect channel, activation/trigger direction, recipient, own-team/opponent restrictions, level availability, probability, duration, cooldown and only calculable uptime.
3. Add hard constraints and opportunity costs: formation/attribute/type/position restrictions, manual operation, long cooldown, probability, VU dependency and self-debuff.
4. Attach multiple scene tags: breakthrough/capture, defense, low-operation commute, expedition/continuous link, visit-count event, score/EXP and growth.
5. Validate exact component coverage, deterministic anomalies and a stratified sample. Unknown or VU-unrecorded values stay unknown rather than becoming zero.
6. Add recommendation-page priors and observed team screenshots only as separate calibration evidence. Detail wiki pages remain the factual authority.

First deliverable: schema + deterministic generator + compact JSONL + validation/manifest, not a UI. A Chinese scenario/role review report may follow only after the profile data is stable.

Current outputs:

- `schemas/role_profile.schema.json`
- `pipeline/profiles/build_role_profiles.py`
- `pipeline/profiles/test_role_profile_regressions.py`
- `pipeline/profiles/run_step3_checks.py`
- `data/role_profiles/role_profiles.jsonl`
- `data/role_profiles/manifest.json`
- `data/role_profiles/validation.json`
- `data/review_queue/step3_role_profile_review.jsonl`
- `data/audits/step3_external_strategy_prior_audit.json`
- `data/audits/step3_role_profile_sample_audit.json`
- `data/audits/step3_role_profile_schema_audit.json`
- `data/reports/step3_role_profile_scenarios_zh.html`
- `data/role_profiles/denko_ratings.jsonl`
- `data/role_profiles/rating_manifest.json`
- `data/audits/step3_denko_rating_audit.json`
- `data/reports/step3_denko_ratings_zh.html`

Status: profile and comparative-rating layers are implemented. The rating is specialization-friendly and roster-relative rather than a context-free truth: it keeps seven scene scores and all component factors, while Step4 still makes the final team/context decision. Resumable observed-case ingestion remains the next source for calibrating model priors, separate from factual ingestion.

### Step 4: Solver

Path: `steps/step4_solver/`

Goal:

- Implement constrained team search.
- Build a user goal, main-denko and scene-specific scoring projection from Step3 profiles.
- Enforce hard constraints before scoring; calculate probabilities, uptime and opportunity cost only where the facts permit.
- Output Pareto teams with Chinese explanations, inactive-skill reasons, alternatives and unresolved facts.
- Keep observed teams as calibration/cases, never as unconditional ground truth.

First implementation slice:

1. Freeze a small, versioned request/result contract with a fixed main denko, scene, level, slots, ownership/exclusions and explicit world/opponent context.
2. Select only scene-relevant Step3 components, verify whether each can actually benefit the main denko, and keep unavailable effects as explanations rather than scoring them.
3. Separate capture, defense, economy and mobility contribution vectors; probability uses an expected value only when its effect amount is known, while manual skills stay an explicit burst alternative.
4. Enumerate a bounded candidate pool and return Pareto alternatives such as maximum immediate contribution, lower-operation and higher-stability teams.
5. Add deterministic regressions for self-only exclusion, formation breakage, actor/station/opponent attribute restrictions, probability weighting, manual activation, and preventing defense-only effects from leaking into capture scores.

Current implementation:

- `schemas/solver_request.schema.json`, `schemas/solver_result.schema.json`, `pipeline/solver/solve_team.py` and deterministic example requests provide a versioned request/result boundary.
- The solver reads only `data/role_profiles/role_profiles.jsonl`, uses scene-specific vectors, applies only known exact probability as expectation, preserves probability ranges as unquantified, and returns bounded Pareto alternatives with per-component source references.
- Known recipient, actor/station attribute, holder-versus-team access, own-team stat-loss, weather, temperature bands, weekday, season/month, time-window, link-time, opponent count and basic all-attribute constraints are checked before numeric contribution. Unsupported constraints become `pending_context`, never free score.
- `pipeline/solver/run_step4_checks.py` produces `data/audits/step4_solver_audit.json`; its condition-coverage section is the controller feedback queue for future solver rule expansion.
- `data/reports/step4_solver_examples_zh.html` is a Chinese, source-linked review page for deterministic capture/defense examples. It is a verification artifact, not a final user UI.

Immediate acceptance gate:

1. Add the high-impact remaining structured constraints: full formation/type/position rules, invalidation scope, opponent diversity and condition-dependent branch values.
2. Add pair/synergy evaluation for probability/CD/effect-amount modifiers, film/accessory effects and positional interactions without double counting a holder's own skill.
3. Ingest the user-account/team ZIP resumably when it is attached; evaluate it only as calibration and explanation evidence.
4. Run real user scenarios through the solver, convert every confirmed mismatch into a source-backed DB/backfill fix or a regression, then expose a request UI/API.

Status: first deterministic solver slice is complete and audited (`19` fixed regressions, `3` live example requests, `issue_count = 0`). Observed-case ZIP ingestion is a parallel calibration track, not a prerequisite for this slice.

### Step 5: UI / Agent

Path: `steps/step5_ui_agent/`

Goal:

- Chinese display layer.
- Read small indexes and records first.
- Explain active/inactive skills, priors, and observed cases.
- Accept fixed denko, scenario, ownership/level constraints and mechanism questions; do not require a full team input.
- Keep result caches keyed by input facts hash so stale solver conclusions cannot silently survive DB updates.

Current local prototype:

- `pipeline/ui/serve_solver.py` serves a Chinese request form at `http://127.0.0.1:8765`.
- The browser sends a versioned solver request and renders the returned active, pending-context, and inactive components separately; it has no independent scoring logic.
- Local API smoke test is green against the current profiles: page `200`, `/api/solve` `200`, and a valid capture request returns bounded Pareto teams with a source-profile cache key.
- Ownership, duplicate/slot, position, saved-request, prior/case comparison, and publication remain Step5 follow-up work.

### Step 6: Calibration And Maintenance

Path: `steps/step6_calibration/`

Goal:

- Ingest observed teams/screenshots resumably as `observed_case` data, including image/OCR provenance and human correction history.
- Compare solver suggestions with cases and recommendation priors without treating either as truth.
- Add scenario-specific evaluation sets and recalibrate weights/constraints only when detail-page facts support the interpretation.
- Re-run narrow audits whenever Step1 fact parsing changes; do not re-fetch or re-parse unchanged wiki content.
- Current intake is metadata-only: `pipeline/calibration/ingest_observed_cases.py` scans ZIP entries into `data/observed_cases/ingest_queue.jsonl` with per-archive and per-entry hashes. It does not extract, OCR, or promote cases into facts.

## External Inputs

- Wiki detail pages: factual authority for skills and character facts.
- Beginner recommendation pages and external strategy articles: `recommendation_prior` / quality-check evidence only; their evaluation criteria and update age must be preserved.
- Observed high-level teams and user-account exports: `observed_case` / calibration evidence only. Ingest resumably from an attachment when it is present under `data/observed_cases/`; no attachment is currently required to build the Step3 foundation.

## Working Rule

When working on a step, only load that step's README/manifest plus directly referenced schemas/data unless there is a concrete reason to inspect another step.
