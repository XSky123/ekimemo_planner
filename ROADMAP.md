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

- Current step: `step3_role_profiles`
- Legacy agent: protected in `archive/legacy_agent_2026-06-06/`
- Git repo: active on branch `main`; static reports are published from the minimal `pages` branch.
- Step 1 state: complete and incrementally updated through `original` 001-165, `extra` 001-128, Another AD02-03, IKS0-6, EKICO EC1-4 and アワメモ OR0. Canonical DB lives under `data/step1_db/`.
- Step 2 state: candidate discovery is complete enough to feed role profiles. Reports remain maintainable views, not final team scores.
- Working tree note: the latest metric/range/VU cleanup must be committed before starting a large Step3 implementation.
- Active TODO: `steps/step3_role_profiles/TODO.md`; Step2 decisions are closed in `steps/step2_indexes/CLOSEOUT.md`.

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
  - `data/reports/step2_prototype_lookup_zh.html`

Status: complete for candidate discovery; keep semantic audits green when Step1 changes.

### Step 3: Role Profiles

Path: `steps/step3_role_profiles/`

Goal:

- Convert facts into reusable role profiles.
- Do not bind profiles to one fixed main denko.
- Normalize uptime, expected effect, trigger actor/direction, recipient, hard constraints, opportunity cost, and scene tags.
- First deliverable: schema + deterministic generator + compact JSONL, not a UI.

### Step 4: Solver

Path: `steps/step4_solver/`

Goal:

- Implement constrained team search.
- Score by scene.
- Output Pareto teams with explanations.

### Step 5: UI / Agent

Path: `steps/step5_ui_agent/`

Goal:

- Chinese display layer.
- Read small indexes and records first.
- Explain active/inactive skills, priors, and observed cases.

## Working Rule

When working on a step, only load that step's README/manifest plus directly referenced schemas/data unless there is a concrete reason to inspect another step.
