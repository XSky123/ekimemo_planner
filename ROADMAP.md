# Roadmap

This project is organized by step to reduce AI context cost and handoff errors.

Global read order:

1. `cache/project_rules.json`
2. `ROADMAP.md`
3. `PROJECT_STRUCTURE.md`
4. Current step README under `steps/`
5. Current step manifest/rules only
6. Relevant schema and targeted data rows

## Current Status

- Current step: `step2_indexes`
- Legacy agent: protected in `archive/legacy_agent_2026-06-06/`
- Git repo: active on branch `main`; static reports are published from the minimal `pages` branch.
- Step 1 state: complete and incrementally updated through `original` 001-165 and `extra` 001-128. Canonical DB lives under `data/step1_db/`.
- Step 2 state: candidate discovery reports are available for attack, experience/PT, defense/support, mobility/visit count, and prototype lookup.

## Steps

### Step 0: Protect Legacy Agent

Path: `steps/step0_protect_legacy/`

Done:

- Archived previous agent spec and rule files.
- Do not edit archived files in place.

### Step 1: Data Reading

Path: `steps/step1_data_reading/`

Goal:

- Read Original + Extra wiki data.
- Build raw cache, cleaned records, first indexes, and review queue.
- Do not run solver.

Key outputs:

- `data/step1_db/denko_facts.jsonl`
- `data/step1_db/skill_facts.jsonl`
- `data/step1_db/denko_index.json`
- `data/step1_db/manifest.json`
- `data/step1_db/validation.json`
- Batch/intermediate provenance remains under `data/records/`, `data/indexes/`, and `data/review_queue/`.

Execution checklist:

- `steps/step1_data_reading/checklist.md`

### Step 2: Indexes And Candidate Discovery

Path: `steps/step2_indexes/`

Goal:

- Build searchable indexes from cleaned records.
- Keep recommendation priors and observed team cases separate from facts.
- Generate candidate reports before solver scoring:
  - `data/reports/step2_attack_support_rankings_zh.html`
  - `data/reports/step2_exp_pt_support_rankings_zh.html`
  - `data/reports/step2_defense_support_rankings_zh.html`
  - `data/reports/step2_mobility_visit_rankings_zh.html`
  - `data/reports/step2_prototype_lookup_zh.html`

### Step 3: Role Profiles

Path: `steps/step3_role_profiles/`

Goal:

- Convert facts into reusable role profiles.
- Do not bind profiles to one fixed main denko.

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
