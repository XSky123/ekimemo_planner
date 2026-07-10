# Step 2: Indexes And Candidate Discovery

Status: complete for candidate discovery; maintenance only.

Step 1 has produced the canonical DB under `data/step1_db/`.

Goal:

- Build indexes by `denko_id`, name, alias, number, pool, attribute, type, effect tag, trigger phase, and condition tag.
- Keep `recommendation_prior` separate from facts.
- Keep `observed_team_case` separate from facts.
- Produce candidate discovery reports that can feed later role profiles and solver scoring.

Current report outputs:

- `data/reports/step2_all_reports_zh.html`
- `data/reports/step2_attack_support_rankings_zh.html`
- `data/reports/step2_exp_pt_support_rankings_zh.html`
- `data/reports/step2_defense_support_rankings_zh.html`
- `data/reports/step2_mobility_visit_rankings_zh.html`
- `data/reports/step2_skill_utility_reports_zh.html`
- `data/reports/step2_prototype_lookup_zh.html`

Current report scripts:

- `pipeline/analysis/write_attack_support_rankings.py`
- `pipeline/analysis/write_exp_pt_support_rankings.py`
- `pipeline/analysis/write_defense_support_rankings.py`
- `pipeline/analysis/write_mobility_visit_rankings.py`
- `pipeline/analysis/write_skill_utility_reports.py`
- `pipeline/analysis/build_step2_reports.py`

Step2 closeout decisions are summarized in `steps/step2_indexes/CLOSEOUT.md`. Active scoring work is tracked only in `steps/step3_role_profiles/TODO.md` and should be implemented as role-profile fields rather than more report-only ranking patches.
