# Ekimemo Manual Semantic Fill Agent

Purpose: handle one ambiguous denko/page at a time and produce a source-backed semantic patch proposal.

This agent may write only proposed patch JSONL records under `data/manual_fills/`. It must not directly edit `data/records/`, parser code, or raw cached pages.

## Inputs

For each requested denko, provide:

- batch HTML report path, usually `data/reports/<batch>_batch_review_zh.html`
- skill fact JSONL path
- denko fact JSONL path
- review queue JSONL path
- target `denko_id`
- optional `component_id` or suspicious reason

The HTML report is the entry point. Use it to understand what the user sees, then inspect only the relevant JSONL row and raw row snippets inside that record.

## Mission

Produce a proposed manual semantic patch when deterministic parser output is incomplete or ambiguous.

Good use cases:

- Labeled components were split incorrectly.
- A target is ambiguous between `self`, `team_all`, `accessing_denko`, `relative_car`, or opponent.
- A condition belongs in `target_filters`, not `target_scope`.
- Attribute words are displaced by a merged-cell table, for example appearing after the sentence instead of inside the blanks.
- Parsed `effect_kind` contradicts the Japanese effect text, for example `condition_raw` says `経験値とスコア獲得` but the component is parsed as `def_debuff`.
- Lv30/Lv50 values are present in raw rows but missing from a component.
- VU-only effects need explicit `availability`.
- Weather, weekday, time, battery, link, station ownership, opponent formation, or mileage conditions need structured hints.
- The page has a special template where a parser rule would be too risky right now.

Bad use cases:

- Full wiki page summarization.
- Re-parsing an entire batch.
- Guessing values that are not in the detail-page row.
- Applying a patch without evidence.

## Patch Contract

Write JSONL to:

`data/manual_fills/<batch>_semantic_patches.jsonl`

Each line must match `schemas/manual_skill_semantic_patch.schema.json`.

Required idea:

- `patch_id`: stable unique id.
- `status`: usually `proposed`.
- `denko_id`, `name`, `detail_url`.
- `source_authority`: normally `detail_page`.
- `evidence`: exact minimal Japanese source text and field path.
- `problem_zh`: what is wrong in current parser output.
- `patch`: structured field-level changes.
- `confidence`: `high`, `medium`, or `low`.
- `needs_parser_rule`: true if this should become a generalized parser rule.
- `reason_zh`: why the patch is justified.

## Field Guidance

Use existing skill component keys:

- `component_id`
- `effect_kind`
- `effect_role`
- `condition_label`
- `condition_raw`
- `target_scope`
- `target_filters`
- `trigger_conditions`
- `scaling_conditions`
- `availability`
- `values_by_denko_level`
- `review_reasons`

Do not translate Japanese raw values. Chinese belongs in `problem_zh`, `reason_zh`, and optional display notes.

## Review Checklist

Before writing a patch, check:

- Does the HTML report show a blank Lv30/Lv50? If VU-only, set `availability.vu_only=true`; if not, patch missing level values or flag parser failure.
- Do labels `(1)`, `(2)`, `(3)` align with component ids and table values?
- Is a referenced label like `(2)(1)` a new effect or a reference to a previous effect?
- Is the receiver explicit? If source says `アクセスしたでんこに`, use `target_scope=["accessing_denko"]`.
- Is `編成内` a target or only a team-count condition?
- Is `相手` a target/condition for the opponent, not own team?
- Are trailing attributes such as `cool属性 heat属性` filling blanks in the condition sentence?
- Does `effect_kind` match Japanese effect words? `経験値` -> `exp_gain`; `スコア獲得` -> `score_gain`; `DEF-10%` -> `def_debuff`; `ATK+` -> `atk_buff`.
- If the text says `リブートしなかったら`, represent that as a no-reboot trigger/outcome condition; do not reuse an unrelated numeric DEF/ATK component.
- Are active access, being accessed, link, battery use, station ownership, time, weather, weekday, and VU conditions represented?
- If unsure, keep `confidence=low`, add a review reason, and do not invent numeric values.

## Output Summary

After writing patches, return in Chinese:

- file written
- count of patch lines
- denko/component ids patched
- which patches are safe manual corrections
- which should become parser rules later
