# Batch Review Agent Task

Use `.agents/batch_review_expert.md` as the role prompt.

请复查本批 ingestion 结果，输出中文报告。重点看高风险项，不要读取全库或整页 wiki。

## Paths

- report: `data\reports\original_080_119_batch_review_zh.html`
- skill_facts: `data/records/original_080_119_skill_facts.jsonl`
- denko_facts: `data/records/original_080_119_denko_facts.jsonl`
- review_queue: `data/review_queue/original_080_119_review_queue.jsonl`

## Observed Cases

- `data\observed_cases\ingestion_cycle_review_rules_2026-06-07.jsonl`
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
    "component_id": "def_buff_1",
    "condition_label": "(1)",
    "denko_id": "original:091",
    "effect_kind": "def_buff",
    "name": "岩切よしの",
    "reasons": [
      "attribute_branch_effect_needs_review"
    ],
    "reasons_zh": [
      "属性分支需要复查"
    ]
  },
  {
    "component_id": "def_debuff_2",
    "condition_label": "(2)",
    "denko_id": "original:091",
    "effect_kind": "def_debuff",
    "name": "岩切よしの",
    "reasons": [
      "condition_effect_mismatch_needs_review"
    ],
    "reasons_zh": [
      "日文效果词与组件类型矛盾"
    ]
  },
  {
    "component_id": "damage_reduction_3",
    "condition_label": "(3)",
    "denko_id": "original:109",
    "effect_kind": "damage_reduction",
    "name": "小涌谷あすか",
    "reasons": [
      "attribute_branch_effect_needs_review"
    ],
    "reasons_zh": [
      "属性分支需要复查"
    ]
  },
  {
    "component_id": "seasonal_damage_reduction_winter",
    "condition_label": null,
    "denko_id": "original:111",
    "effect_kind": "damage_reduction",
    "name": "糸魚川せつか",
    "reasons": [
      "condition_effect_mismatch_needs_review"
    ],
    "reasons_zh": [
      "日文效果词与组件类型矛盾"
    ]
  },
  {
    "component_id": "seasonal_fixed_damage_summer",
    "condition_label": null,
    "denko_id": "original:111",
    "effect_kind": "fixed_damage",
    "name": "糸魚川せつか",
    "reasons": [
      "condition_effect_mismatch_needs_review"
    ],
    "reasons_zh": [
      "日文效果词与组件类型矛盾"
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