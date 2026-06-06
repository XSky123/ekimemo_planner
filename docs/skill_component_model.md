# Skill Component Model

Purpose: represent one denko skill as multiple atomic solver-facing effects.

This model is for team building. A single wiki skill may contain several independent useful effects, for example:

- team ATK increase
- self ATK increase
- team EXP increase
- self EXP increase
- Lv92+ additional probability or extra condition
- fixed damage plus damage reduction
- activation probability boost, for example a VU-only `(2)` effect that increases trigger probability based on team composition

Do not collapse these into one `effect_kind` list. Store them as separate `skill_components`.

## Core Shape

Each `skill_fact` may contain:

- `skill_components`: array of atomic effects.
- `values_by_denko_level`: raw expanded skill-level rows for the whole skill.
- `lv50`: compatibility shortcut only.

## Key Levels

Only these denko levels should be treated as key skill/value checkpoints:

- `1`
- `15`
- `30`
- `50`
- `60`
- `70`
- `80`
- `92`
- `96`
- `100`

Levels `92`, `96`, and `100` are VU-specific and should only appear when the denko/page has VU data. For early practical team building, prioritize levels `30` and `50`: one newly obtained denko usually caps at `50`, and level `30` is the important pre-cap comparison point.

Each `skill_component` contains:

- `component_id`: stable local id such as `atk_buff`, `exp_gain`, or `damage_reduction`.
- `effect_kind`: normalized effect type.
- `target_scope`: who receives the effect, for example `team_all`, `self`, `front_car`, `own_team`, `opponent_team`.
- `target_filters`: attribute/type/position filters, for example `{ "attribute": "cool" }`.
- `trigger_conditions`: structured trigger hints, for example HP threshold, access event, time window.
- `activation_type`: raw Japanese activation type.
- `condition_raw`: raw Japanese condition/effect text.
- `remarks_raw`: raw Japanese remarks.
- `values_by_denko_level`: per-level values for this component.
- `confidence`, `needs_review`, `review_reasons`.

## Per-Level Value Shape

Each component value keeps:

- `value_raw`: Japanese value text.
- `value_numeric`: parsed number if safe.
- `unit`: `percent`, `percent_hp`, `flat_exp`, `flat_damage`, `count`, `duration`, `boolean`, etc.
- `probability`: raw Japanese probability columns.
- `duration`: raw Japanese duration.
- `cooldown`: raw Japanese cooldown.
- `skill_level`: raw Japanese skill level label.
- `source_text`: raw Japanese comment.
- `raw_row`: full expanded table row.

## Authority Rule

Reverse lookup tables can suggest which denko may have a component. Detail pages confirm component values, duration, cooldown, probability, and exact conditions.

## Review Rule

Mark `needs_review = true` when:

- one text span contains multiple effects,
- Lv92+ adds new condition/probability/effect,
- target scope is inferred from Japanese prose,
- value parsing is numeric but not yet manually verified,
- the effect depends on weather, temperature, station, mileage, position, opponent, or current team composition.
