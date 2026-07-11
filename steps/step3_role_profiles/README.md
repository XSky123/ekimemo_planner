# Step 3: Role Profiles

Status: complete and ready for Step4 consumption.

Active checklist: `steps/step3_role_profiles/TODO.md`.

Start only after Step 2 indexes are available. Step3 itself is complete: use the generated profiles through their manifest and validation rather than reparsing Step1 during solver work.

Goal:

- Convert cleaned skill facts into reusable role profiles.
- Score general scene fit and publish a cross-character comparative rating.
- Preserve confidence and review reasons in every derived record.

Do not bind a profile to a single fixed main denko.

## First Increment

1. Define `schemas/role_profile.schema.json`.
2. Generate one profile per skill component from `data/step1_db/skill_facts.jsonl`.
3. Preserve `source_url`, component id, confidence, review reasons and DB lock provenance.
4. Add normalized fields for effect channel, trigger actor/direction, recipient, hard conditions, activation probability, duration, cooldown and estimated uptime.
5. Keep reusable scene tags, then derive a separate versioned rating layer. Component utility combines effect magnitude, activation probability, time coverage, condition satisfiability, recipient scope and opportunity cost.
6. Publish both a Wiki-calibrated Lv50 beginner rating and an independent Lv80 veteran rating. Keep the raw Lv50 fact-model score visible for disagreement review.
7. Score seven practical scenes independently: daily attack, planned burst, home defense, expedition score, expedition EXP, routine growth and mechanism support.

Outputs:

- `data/role_profiles/role_profiles.jsonl`
- `data/role_profiles/manifest.json`
- `data/role_profiles/validation.json`
- `data/role_profiles/denko_ratings.jsonl`
- `data/role_profiles/rating_manifest.json`
- `data/reports/step3_role_profile_scenarios_zh.html`
- `data/reports/step3_denko_ratings_zh.html`
- `data/audits/step3_rating_llm_round1.jsonl`
- `data/audits/step3_rating_llm_round2.jsonl`
- `data/audits/step3_rating_llm_two_round_audit.json`

## Rating formula

For component `c` at level `L`:

`utility(c,L,scene,stage) = impact × absolute_magnitude_anchor × probability × scene_availability × stage_condition × scope × cost`

- A missing duration and cooldown means an event-bound/passive effect and uses coverage `1`; known timed skills use the cycle coverage above.
- Sustained scenes use cycle coverage; planned burst uses a separate readiness factor so a short high-impact skill is not judged like an all-day passive.
- Lv50 heavily discounts Mileage Class 10 rosters, accessory slots/collections, link-success prerequisites and mono-attribute growth targets. Lv80 relaxes progression costs but does not remove factual conditions.
- Numeric magnitude uses fixed per-effect anchors, so a tiny unconditional buff no longer receives a high score merely because many characters have no buff.
- The Wiki `×/△/○/◎` marker selects the coarse published beginner band; the fact model ranks within it. `※` remains contextual. Raw disagreements retain the Japanese Wiki reason and a Chinese model reason in the audit.

Normal local rebuild and regression:

```powershell
python pipeline/profiles/run_step3_checks.py
```

To refresh only the two beginner recommendation priors before the same checks, use
`python pipeline/profiles/run_step3_checks.py --refresh-priors`. The recommendation
pages remain priors; detail pages stay the factual authority.

The two LLM audit rounds are preserved review evidence, not regenerated templates.
Each round contains the top 15 and bottom 15 eligible candidates for all seven
scenes. The report displays their actual review text; unreviewed rows show only
structured factors and no generated recommendation sentence.
