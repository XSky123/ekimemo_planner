# Wiki Table Parsing

Wiki tables may contain merged cells. The Step 1 parser must be table-aware for both list pages and detail pages.

## Algorithm

1. Parse HTML into DOM.
2. Select the main denko list table by header names, not by position alone.
3. Iterate rows and expand cells into a matrix:
   - Before placing current row cells, fill slots carried by active rowspans.
   - Honor `rowspan` and `colspan`.
   - Record whether a cell is direct or inherited.
4. Normalize headers.
5. Skip repeated header rows.
6. Emit a record only when the expanded row has a valid `wiki_no`.
7. Validate required fields: `wiki_no`, linked `name`, `detail_url`, `type`, `attribute`, `color`, `skill_name`.
8. Send malformed or ambiguous rows to `review_queue`.

## Detail Pages

Confirmed: denko detail pages can also contain merged cells and many nested or collapsed tables. For example, a checked detail page had multiple tables plus both `rowspan` and `colspan`.

Detail page parsing must:

- Select sections by headings and nearby labels, not by table order alone.
- Expand every table with the same matrix algorithm before extracting skill level, status, wrapping, or profile fields.
- Preserve section context such as `skill`, `ステータス詳細`, `ラッピング`, and collapsed region title.
- Treat hidden/collapsed wiki regions as normal source content if present in HTML.
- Never merge skill level rows by visual line breaks alone.
- Put ambiguous section/table matches into `review_queue`.

## Screenshot / Visual Confirmation

If HTML parsing and text evidence are not enough to prove a field was read correctly, the parser/reviewer should capture visual evidence.

Use screenshot confirmation when:

- A table has merged cells and the expanded matrix does not match expected headers.
- A field appears in multiple candidate sections.
- Skill level values, VU values, duration, cooldown, or probability columns are ambiguous.
- The rendered page differs from raw HTML text order.
- A human reviewer asks to confirm layout.

Screenshot evidence should be stored under `data/review_evidence/screenshots/` and referenced from the review queue item. Do not store screenshots as facts; screenshots are evidence for review.

## Why This Matters

Original denko list rows can share `備考` via `rowspan`. A naive parser that maps raw `<td>` positions will shift columns and corrupt ids, names, or skill fields.

## Debug Fields

Temporary parser debug output may include:

- `table_index`
- `row_index`
- `expanded_column_count`
- `cell_origin_by_column`
- `raw_html_snippet`
- `screenshot_path`
- `rendered_section_label`

These fields are for parser review and should not be required by solver records.
