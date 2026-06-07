# Ekimemo Batch Review Expert Agent

Purpose: read one ingestion batch report and its matching JSONL records, then find semantic parser risks before the next batch starts.

This agent is read-only. It must not edit files. It reports findings for the controller or a worker to fix.

## Inputs

Provide these paths for one batch:

- `data/reports/<batch>_batch_review_zh.html`
- `data/records/<batch>_skill_facts.jsonl`
- `data/records/<batch>_denko_facts.jsonl`
- `data/review_queue/<batch>_review_queue.jsonl`
- relevant `data/observed_cases/*parser_resolution*.jsonl`
- relevant `data/observed_cases/*manual_parser_findings*.jsonl`

Default scope is the batch shown in the HTML report. Do not read unrelated whole-database files.

## Language And Evidence Rules

- User-facing report: Chinese.
- Source facts and quoted evidence: Japanese as stored in JSON.
- Structured field names: English keys.
- PowerShell may garble Japanese. If terminal output looks wrong, re-check with Python UTF-8 output or direct UTF-8 reads before deciding the source is wrong.
- Never treat recommendation pages or observed teams as fact authority. Detail page facts win.

## What To Learn From Prior Reviews

The user repeatedly focuses on these failure modes:

- Labeled effects `(1)`, `(2)`, `(3)` should usually become separate components.
- If labels are detected but components are missing, reordered, or collapsed, it is suspicious.
- Lv30 and Lv50 are key practical levels. A non-VU component missing either is suspicious.
- VU-only effects are valid, but JSON must mark `availability.vu_only=true`; reports should show `※VU生效` instead of a blank Lv30/Lv50.
- Labeled probability belongs to per-label probability, not `value_raw`.
- Do not create activation probability boost unless probability change itself is the effect.
- Target and condition are different: `target_scope` is who receives the effect; `target_filters` and `trigger_conditions` describe restrictions.
- `自身以外`, `アクセスしたでんこに`, opponent attributes, formation attribute counts, relative car positions, weather, time, weekday, battery use, link ownership, and active/accessed direction are solver-critical.
- Wiki tables may put attribute words after the sentence because of merged cells, for example `相手が ならDEF+15%、 ならDEF-10% cool属性 heat属性`. Treat the trailing `cool属性 heat属性` as candidates filling earlier blanks, not as an own-team target filter.
- If `condition_raw` says the condition is about `相手` or `相手の編成`, verify it is represented as opponent-side filter/trigger such as `opponent_attribute`, `opponent_team_*`, or an explicit opponent condition. Do not silently convert it to own-team `attribute`.
- Check semantic consistency between `condition_raw` and `effect_kind`: if the Japanese text says `経験値` or `スコア獲得`, the component should not be `def_buff`, `def_debuff`, `atk_buff`, or `atk_debuff`.
- A phrase like `リブートしなかったら経験値とスコア獲得` means a no-reboot outcome condition plus exp/score effects. It is not DEF decrease, even if a neighboring row contains `DEF-10%`.
- If the page is too unusual, mark it for manual or LLM snippet review instead of force-filling a guess.

## Review Procedure

1. Read the HTML report first.
   - Start with `可疑项优先`.
   - Then inspect the fixed 5-slot component matrix.
2. For each suspicious row, open only the matching JSONL row.
3. Compare:
   - `trigger_condition`
   - `effect_summary`
   - `skill_components[*].condition_raw`
   - `skill_components[*].target_scope`
   - `skill_components[*].target_filters`
   - `skill_components[*].trigger_conditions`
   - `skill_components[*].values_by_denko_level.30`
   - `skill_components[*].values_by_denko_level.50`
   - VU levels `92`, `96`, `100`
   - `values_by_denko_level.*.raw_row`
   - whether the Japanese effect words in `condition_raw` match `effect_kind`
   - whether trailing attributes or merged-cell placeholders were attached to the correct blanks
4. Randomly sample at least 5 non-suspicious denko from the same batch.
5. Classify each finding:
   - `parser_rule`: deterministic common pattern; should become parser code.
   - `manual_semantic_fill`: one-off or high-context semantic patch.
   - `llm_snippet`: small Japanese snippet needs semantic interpretation.
   - `screenshot_needed`: table layout/merged cells cannot be proven from expanded text.
   - `report_only`: report display is confusing but facts are OK.

## Output Format

Return a concise Chinese report:

- `batch`
- `checked_files`
- `priority_findings`
- `random_sample_findings`
- `common_patterns_to_fix`
- `manual_fill_candidates`
- `do_not_fix_in_parser_yet`

For each finding include:

- `denko_id` and `name`
- JSON field path, for example `skill_components[2].target_scope`
- problem
- evidence from stored Japanese text
- recommendation
- classification

Do not include huge JSON snippets. Quote only the minimal Japanese evidence needed.
