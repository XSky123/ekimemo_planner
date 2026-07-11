# Step3 Active TODO

Updated: 2026-07-11

## Deliverable

Build deterministic role profiles from `data/step1_db/skill_facts.jsonl`:

- `schemas/role_profile.schema.json`
- `pipeline/profiles/build_role_profiles.py`
- `data/role_profiles/role_profiles.jsonl`
- `data/role_profiles/manifest.json`
- `data/role_profiles/validation.json`

## Implementation Order

1. [done] Define one profile row per skill component and preserve DB provenance/locks.
2. [done] Normalize effect channel, trigger actor, access direction, recipient and opponent/own-team constraints.
3. [done] Normalize level availability, probability, duration, cooldown and estimated uptime without inventing missing values.
4. [done] Add hard conditions and costs: attribute/type composition, position, manual activation, long cooldown, VU dependency and self-debuff.
5. [done] Add multi-label scene tags for capture, defense, commute, expedition, visit-count events, score farming and 育成.
6. [done] Validate every Step1 component is represented once or explicitly excluded with a reason.
7. [done] Add a fixed regression suite covering manual, probability, accessed trigger, weather/temperature, VU, random access, nullification, self-debuff and special-pool branches.
8. [done] Produce the Chinese scenario role-profile report with independent beginner-recommendation prior status.
9. [done] Resolve the profile review queue through deterministic rules and stable source backfills; current generated queue count is zero. Do not mass-clear future source flags.
10. [next] Ingest user-account/team ZIP data resumably under `data/observed_cases/` when the attachment is available, then keep it as calibration evidence separate from facts.
11. [done] Add a small, stratified comparison against the external 3secondsgameover attacker/formation articles; store only reusable scenario claims and update dates, not article text.
12. [done] Replace the prior no-score Step3 boundary with a versioned comparative rating layer covering probability, uptime/CD, condition satisfiability, scope, costs and effect magnitude.
13. [done] Generate 307 Lv50/Lv80 character ratings, scene scores and deterministic Chinese one-line recommendations.
14. [next] Calibrate condition-satisfaction priors and cross-effect impact weights from observed teams/use records; never learn skill facts from those observations.
15. [done] Split scoring into seven actual-use scenes and separate Wiki-calibrated beginner recommendations from independent veteran scores.
16. [done] Backfill progression/link semantics for EX110-112, Original081/083 and accessory-dependent EX118-120; stop treating mutually exclusive station-attribute branches as simultaneous value.
17. [done] Emit every raw Wiki/model disagreement with the original Japanese Wiki reason and a Chinese model explanation; published beginner bands align with all non-contextual Wiki markers.
18. [done] Complete two LLM review rounds over the top 15 and bottom 15 eligible candidates in every scene (210 rows per round, 420 review instances total), backfill discovered Step1 semantics and retune Step3 normalization.
19. [done] Remove generated recommendation prose from the report. Show probability, coverage, activation conditions, scope/cost and both rounds' reviewed comments as explicit columns.

## Scoring Boundary

Step3 may publish a comparative general-purpose rating, but it must keep every scene score and factor decomposition. It is a roster-relative guide, not a substitute for Step4's team/context solver. Step4 remains authoritative for a concrete main denko, owned roster, station/opponent context and requested objective.

## Acceptance

- Schema-valid UTF-8/LF outputs.
- Manifest records source DB hash, generator version and row counts.
- No report-only fact supplements.
- Unknown/VU-unrecorded values remain unknown and do not become zero.
- Trigger actor, access direction and recipient are separate fields.
- Validation has no unexplained missing or duplicate components.
- `pipeline/profiles/run_step3_checks.py` is green: schema audit, 12 fixed regressions, external-prior contract audit and 11 deterministic stratified samples.
- Rating schema/audit and the four formula regressions are green, including the explicit same-10%-effect comparison where always-on beats cooldown/probability/formation-constrained variants.
