# Step 2: Indexes And Candidate Discovery

Status: in progress.

Step 1 has produced the canonical DB under `data/step1_db/`.

Goal:

- Build indexes by `denko_id`, name, alias, number, pool, attribute, type, effect tag, trigger phase, and condition tag.
- Keep `recommendation_prior` separate from facts.
- Keep `observed_team_case` separate from facts.
- Produce candidate discovery reports that can feed later role profiles and solver scoring.

Current report outputs:

- `data/reports/step2_attack_support_rankings_zh.html`
- `data/reports/step2_exp_pt_support_rankings_zh.html`
- `data/reports/step2_defense_support_rankings_zh.html`

Current report scripts:

- `pipeline/analysis/write_attack_support_rankings.py`
- `pipeline/analysis/write_exp_pt_support_rankings.py`
- `pipeline/analysis/write_defense_support_rankings.py`

Do not implement solver here.

