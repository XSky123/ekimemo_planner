# Step 3: Role Profiles

Status: next.

Active checklist: `steps/step3_role_profiles/TODO.md`.

Start only after Step 2 indexes are available.

Goal:

- Convert cleaned skill facts into reusable role profiles.
- Score general scene fit.
- Preserve confidence and review reasons in every derived record.

Do not bind a profile to a single fixed main denko.

## First Increment

1. Define `schemas/role_profile.schema.json`.
2. Generate one profile per skill component from `data/step1_db/skill_facts.jsonl`.
3. Preserve `source_url`, component id, confidence, review reasons and DB lock provenance.
4. Add normalized fields for effect channel, trigger actor/direction, recipient, hard conditions, activation probability, duration, cooldown and estimated uptime.
5. Add scene tags only; do not collapse all scenes into one score.

Proposed output: `data/role_profiles/role_profiles.jsonl` plus a compact manifest and validation file.
