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

1. Define one profile row per skill component and preserve DB provenance/locks.
2. Normalize effect channel, trigger actor, access direction, recipient and opponent/own-team constraints.
3. Normalize level availability, probability, duration, cooldown and estimated uptime without inventing missing values.
4. Add hard conditions and costs: attribute/type composition, position, manual activation, long cooldown, VU dependency and self-debuff.
5. Add multi-label scene tags for capture, defense, commute, expedition, visit-count events, score farming and 育成.
6. Validate every Step1 component is represented once or explicitly excluded with a reason.
7. Review deterministic anomalies and a stratified sample before declaring Step3 ready for the solver.

## Scoring Boundary

Do not create a single global denko score. Step3 describes reusable capabilities and costs; Step4 combines them by scene, team constraints, uptime and opportunity cost.

## Acceptance

- Schema-valid UTF-8/LF outputs.
- Manifest records source DB hash, generator version and row counts.
- No report-only fact supplements.
- Unknown/VU-unrecorded values remain unknown and do not become zero.
- Trigger actor, access direction and recipient are separate fields.
- Validation has no unexplained missing or duplicate components.
