# Project Phases

Canonical step folders live under `steps/`. This file is a compact overview; when executing work, read the matching `steps/<step_name>/README.md` first.

## Phase 0: Protect Legacy Agent

- Keep the previous agent spec and rule files in `archive/legacy_agent_2026-06-06/`.
- Do not edit archived files except to add an explicit newer snapshot.
- Use `cache/project_rules.json` as the low-token handoff entrypoint.

## Phase 1: Data Ingestion And Cleanup

- Collect Original + Extra denko list entrypoints.
- Fetch pages only when cache is missing, stale, low confidence, or explicitly refreshed.
- Store raw wiki/game text in Japanese.
- Parse records into English-key JSON/JSONL structures.
- Generate review queue entries for ambiguous skills, VU differences, weather/time/location conditions, and parser failures.
- Do not run team optimization yet.

## Phase 2: Indexes And Candidate Discovery

- Build indexes by name, alias, number, pool, attribute, type, effect tags, trigger phase, and condition tags.
- Treat recommendation pages as `recommendation_prior` only.
- Treat observed expert teams/screenshots as `observed_team_case` only.

## Phase 3: Role Profiles

- Convert cleaned facts into reusable role profiles.
- Score general scene fit without binding to a specific main denko.
- Keep confidence and review reasons with every derived record.

## Phase 4: Solver

- Use fixed members plus small combination enumeration.
- Apply hard constraints before scoring.
- Project effects into the requested scene; irrelevant effects score 0.
- Output Pareto results, not a single global best team.

## Phase 5: UI / Agent Layer

- Display in Chinese with important Japanese game terms preserved.
- Read indexes and single records first to control token cost.
- Explain why skills are active, inactive, prior-only, or case-only.
