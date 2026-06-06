# Wiki ID Mapping

The Original and Extra denko list pages are the canonical Step 1 source for mapping wiki ids to detail pages.

## Source Pages

- Original: `顔画像・タイプ・属性・色・スキル名/オリジナルでんこ`
- Extra: `顔画像・タイプ・属性・色・スキル名/エクストラでんこ`

Each list row should be parsed into:

- `wiki_no`: source id text from the `No.` column, such as `6` or `EX35`
- `denko_id`: normalized project id, such as `original:006` or `extra:035`
- `id_pool`: `original` or `extra`
- `id_number`: numeric part for sorting and joins
- `name`: linked wiki name text
- `wiki_page_title`: page title inferred from the link target
- `detail_url`: linked detail page URL
- `type`
- `attribute`
- `color`
- `skill_name`
- `vu_marker`
- `remarks`

## Rules

- Keep `wiki_no` exactly as the wiki presents it.
- Use `denko_id` for joins, cache keys, and solver references.
- Do not rely on name alone as a stable key.
- If a detail page and list page disagree, keep both values, mark `needs_review = true`, and resolve through `manual_overrides` with a source and reason.

## Merged Cell Handling

Confirmed: the Original list page uses merged cells such as `rowspan` in the `備考` column. A parser must not assume that each HTML `<tr>` has the same number of `<td>` cells.

Required parsing strategy:

- Parse the actual HTML table, not the rendered text lines.
- Expand `rowspan` and `colspan` into a rectangular table matrix before mapping columns.
- Repeated header rows must be detected and skipped.
- The image column is not part of the identity mapping, but its image alt text may be stored as optional evidence.
- A valid denko row is anchored by a `No.` / `EXxx` cell after matrix expansion.
- For inherited merged cells, store the inherited text normally and optionally mark `cell_origin = inherited_rowspan` in debug output.
- If matrix expansion leaves a row with missing required cells, write it to `review_queue` instead of guessing.

