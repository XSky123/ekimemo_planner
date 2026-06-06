# Detail Page Parsing

Denko detail pages are not guaranteed to use a single stable template. They can contain merged cells, repeated tables, nested/collapsed regions, and section-specific layouts.

## Required Strategy

- Parse HTML into DOM.
- Identify page sections by heading text and local labels.
- Expand `rowspan` and `colspan` for every table before mapping columns.
- Keep Japanese source text as-is in facts.
- Store English keys in structured records.
- Add `source_section`, `table_index`, and `row_index` for fields derived from tables.
- Send ambiguous fields to `review_queue`.

## Evidence Policy

Each low-confidence parsed field should keep at least one of:

- `raw_html_snippet`
- `text_snippet`
- `source_section`
- `screenshot_path`

Use screenshots when visual layout matters or when merged cells make text-only review risky.

## Known Risk Areas

- Skill level tables
- VU-specific skill text
- Status tables
- Wrapping tables
- Probability / duration / cooldown columns
- Collapsed regions
- Multi-effect skills with numbered effects

## Step1 Skill Fact Keys

Current detail-page extraction should first try to populate these fact keys:

- `trigger_condition`: raw Japanese trigger condition from `発動条件` or `発動条件・効果`.
- `effect_summary`: raw Japanese effect summary from `効果` or `発動条件・効果`.
- `activation_type`: raw Japanese `アクティベーションタイプ`.
- `skill_remarks`: raw Japanese `備考`.
- `normalized_skill`: derived semantic hints for solver use, for example effect kind, target scope, HP threshold, and activation mode.
- `lv50.skill_level`: raw Japanese skill level row label, normally `Lv.4 (でんこLv.50)`.
- `lv50.special_explanation`: raw Japanese `コメント` at denko level 50.
- `lv50.effect`: raw Japanese `効果` at denko level 50.
- `lv50.duration`: raw Japanese `効果時間` or `発動時間` at denko level 50.
- `lv50.cooldown`: raw Japanese `クールタイム` or `CD` at denko level 50.
- `lv50.probability`: all raw Japanese columns whose header contains `発動率`.
- `lv50.raw_row`: full expanded raw row for manual review.
- `values_by_denko_level`: all expanded skill-level rows keyed by denko level. This prevents confusing `でんこLv.50` with nearby rows such as `でんこLv.60`.
- `key_level_stats`: AP/HP/Exp at levels `15`, `30`, `50`, `60`, `70`, and `80`.

Keep `lv50` as `null` when the page has no standard skill-level row or the template is special. Keep `key_level_stats` empty when no reliable AP/HP table is found.
