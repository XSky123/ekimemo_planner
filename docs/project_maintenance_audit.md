# Project Maintenance Audit

Date: 2026-07-06

## Encoding And Line Endings

- Repository text defaults are tracked in `.editorconfig`: UTF-8, LF, final newline.
- Local Git config is set to `core.autocrlf=false`, `core.eol=lf`, `core.safecrlf=warn`.
- Local VS Code settings may exist under ignored `.vscode/settings.json` for UTF-8, LF, and Python UTF-8 terminal environment.
- Current-user PowerShell all-host profile has an idempotent UTF-8 defaults block. Existing shells may need restart before it takes effect.

## Current Canonical Scope

- Step1 DB: `data/step1_db/`
- `original`: 001-165
- `extra`: 001-128
- Total: 293 denko facts and 293 skill facts
- Validation: `issue_count = 0`

## Active Reports

- `data/reports/step1_final_report_zh.html`
- `data/reports/step1_human_overview_zh.html`
- `data/reports/step2_attack_support_rankings_zh.html`
- `data/reports/step2_defense_support_rankings_zh.html`
- `data/reports/step2_exp_pt_support_rankings_zh.html`
- `data/reports/step2_mobility_visit_rankings_zh.html`
- `data/reports/step2_prototype_lookup_zh.html`

## Cleanup Done

- Removed stale `docs/ekimemo_scene_recommendations.html`; it was an old 290-row scene prototype with mojibake and no current generator.
- Removed stale `data/agent_runs/original_001_163_report_checklist_audit.*`; current audit output is `original_001_165`.
- Updated `data/reports/step1_final_report_zh.html` from the old 290-row closeout to the current 293-row handoff.
- Updated roadmap and handoff notes so old 290-row numbers are clearly historical.

## Keep Deliberately

- `data/records/`, `data/indexes/`, and `data/review_queue/` retain batch provenance. They are not the canonical DB, but they explain how records were produced.
- `cache/01_reverse_index/`, `cache/02_denko_profile/`, `cache/03_skill_parsed/`, and `cache/04_solver_results/` are legacy/prototype references only. Do not use them as Step1 facts.
- `data/reports/step2_prototype_lookup_sample_zh.html` is a sample report output from the prototype lookup script; it is not linked from the main reports index.

## Remaining Watch Items

- `original_001_165` full checklist audit still reports old-batch issues for `original:001`, `original:016`, and `original:018`; these are not caused by the 2026-07-06 increment and Step1 DB validation remains clean.
- Direct UTF-8 scan found historical mojibake-like text in older Step1 rows: about 17 denko fact rows and 47 skill fact rows. This predates the 2026-07-06 increment and should be handled as a separate old-batch refetch/rebuild task, not by trusting terminal rendering.
- Some old tracked caches/reports are historical artifacts. If repository size becomes a problem, move large historical agent-run audits to an archive step, but do not delete canonical DB or batch provenance without a replacement manifest.
