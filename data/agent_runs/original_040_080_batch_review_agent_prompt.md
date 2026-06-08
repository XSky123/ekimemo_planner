# Batch Review Agent Task

Use `.agents/batch_review_expert.md` as the role prompt.

请复查本批 ingestion 结果，输出中文报告。重点看高风险项，不要读取全库或整页 wiki。

## Paths

- report: `data/reports/original_040_080_batch_review_zh.html`
- skill_facts: `data/records/original_040_080_skill_facts.jsonl`
- denko_facts: `data/records/original_040_080_denko_facts.jsonl`
- review_queue: `data/review_queue/original_040_080_review_queue.jsonl`

## Observed Cases

- `data\observed_cases\ingestion_cycle_review_rules_2026-06-07.jsonl`
- `data\observed_cases\original_040_080_parser_resolution_2026-06-07.jsonl`
- `data\observed_cases\original_040_080_parser_resolution_2026-06-07_round2.jsonl`
- `data\observed_cases\original_040_080_parser_resolution_2026-06-08_round3.jsonl`
- `data\observed_cases\original_080_119_manual_parser_findings.jsonl`
- `data\observed_cases\original_080_119_parser_resolution_2026-06-07.jsonl`
- `data\observed_cases\original_080_119_parser_resolution_2026-06-07_round2.jsonl`
- `data\observed_cases\original_120_163_manual_parser_findings.jsonl`
- `data\observed_cases\original_120_163_parser_resolution_2026-06-07.jsonl`
- `data\observed_cases\original_120_163_parser_resolution_2026-06-07_round2.jsonl`
- `data\observed_cases\original_120_163_parser_resolution_2026-06-07_round3.jsonl`
- `data\observed_cases\original_120_163_parser_resolution_2026-06-07_round4.jsonl`

## Blocking Items

优先确认这些是否是 parser 共性问题、manual fill、还是报告误报：

```json
[
  {
    "component_id": "def_buff",
    "condition_label": null,
    "denko_id": "original:041",
    "effect_kind": "def_buff",
    "name": "南郷にちな",
    "reasons": [
      "condition_effect_mismatch_needs_review"
    ],
    "reasons_zh": [
      "日文效果词与组件类型矛盾"
    ]
  },
  {
    "component_id": "duration_extension_2",
    "condition_label": "(2)",
    "denko_id": "original:061",
    "effect_kind": "duration_extension",
    "name": "深遊ちとせ",
    "reasons": [
      "vu_label_level_mismatch_needs_review"
    ],
    "reasons_zh": [
      "原文声明该编号 Lv92+ 生效，但组件等级不是 VU-only"
    ]
  },
  {
    "component_id": "def_debuff_2",
    "condition_label": "(2)",
    "denko_id": "original:076",
    "effect_kind": "def_debuff",
    "name": "上ノ山ゆのか",
    "reasons": [
      "condition_effect_mismatch_needs_review"
    ],
    "reasons_zh": [
      "日文效果词与组件类型矛盾"
    ]
  },
  {
    "component_id": "atk_buff_2",
    "condition_label": "(2)",
    "denko_id": "original:078",
    "effect_kind": "atk_buff",
    "name": "海部なる",
    "reasons": [
      "compound_labeled_effect_needs_manual_review",
      "condition_effect_mismatch_needs_review",
      "labeled_component_count_mismatch"
    ],
    "reasons_zh": [
      "复合编号需要片段复查",
      "日文效果词与组件类型矛盾",
      "编号标签与组件不匹配"
    ]
  }
]
```

## Required Output

- batch
- priority_findings
- random_sample_findings
- common_patterns_to_fix
- manual_fill_candidates
- do_not_fix_in_parser_yet