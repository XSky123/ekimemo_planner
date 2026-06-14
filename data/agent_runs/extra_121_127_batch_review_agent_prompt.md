# Batch Review Agent Task

Use `.agents/batch_review_expert.md` as the role prompt.

请复查本批 ingestion 结果，输出中文报告。重点看高风险项，不要读取全库或整页 wiki。

## Paths

- report: `data\reports\extra_121_127_batch_review_zh.html`
- skill_facts: `data/records/extra_121_127_skill_facts.jsonl`
- denko_facts: `data/records/extra_121_127_denko_facts.jsonl`
- review_queue: `data/review_queue/extra_121_127_review_queue.jsonl`

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
    "component_id": "score_gain_2",
    "condition_label": "(2)",
    "denko_id": "extra:121",
    "effect_kind": "score_gain",
    "name": "コニー・クラークデール",
    "reasons": [
      "duplicate_labeled_component_values_need_review"
    ],
    "reasons_zh": [
      "多个编号组件值重复，疑似错位"
    ]
  },
  {
    "component_id": "score_gain_3",
    "condition_label": "(3)",
    "denko_id": "extra:121",
    "effect_kind": "score_gain",
    "name": "コニー・クラークデール",
    "reasons": [
      "condition_effect_mismatch_needs_review",
      "duplicate_labeled_component_values_need_review"
    ],
    "reasons_zh": [
      "日文效果词与组件类型矛盾",
      "多个编号组件值重复，疑似错位"
    ]
  },
  {
    "component_id": "hp_recovery_2",
    "condition_label": "(2)",
    "denko_id": "extra:122",
    "effect_kind": "hp_recovery",
    "name": "マリリン・マクリーン",
    "reasons": [
      "compound_labeled_effect_needs_manual_review",
      "labeled_component_count_mismatch"
    ],
    "reasons_zh": [
      "复合编号需要片段复查",
      "编号标签与组件不匹配"
    ]
  },
  {
    "component_id": "reboot_4",
    "condition_label": "(4)",
    "denko_id": "extra:122",
    "effect_kind": "reboot",
    "name": "マリリン・マクリーン",
    "reasons": [
      "compound_labeled_effect_needs_manual_review",
      "labeled_component_count_mismatch"
    ],
    "reasons_zh": [
      "复合编号需要片段复查",
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