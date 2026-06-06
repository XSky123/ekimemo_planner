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

