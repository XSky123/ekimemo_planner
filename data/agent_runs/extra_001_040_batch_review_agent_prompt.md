# Batch Review Agent Task

Use `.agents/batch_review_expert.md` as the role prompt.

请复查本批 ingestion 结果，输出中文报告。重点看高风险项，不要读取全库或整页 wiki。

## Paths

- report: `data\reports\extra_001_040_batch_review_zh.html`
- skill_facts: `data/records/extra_001_040_skill_facts.jsonl`
- denko_facts: `data/records/extra_001_040_denko_facts.jsonl`
- review_queue: `data/review_queue/extra_001_040_review_queue.jsonl`

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
    "component_id": "damage_reduction",
    "condition_label": null,
    "denko_id": "extra:007",
    "effect_kind": "damage_reduction",
    "name": "仰図まや",
    "reasons": [
      "condition_effect_mismatch_needs_review"
    ],
    "reasons_zh": [
      "日文效果词与组件类型矛盾"
    ]
  },
  {
    "component_id": "atk_debuff_1",
    "condition_label": "(1)",
    "denko_id": "extra:008",
    "effect_kind": "atk_debuff",
    "name": "阿下喜ケイ",
    "reasons": [
      "condition_effect_mismatch_needs_review"
    ],
    "reasons_zh": [
      "日文效果词与组件类型矛盾"
    ]
  },
  {
    "component_id": "def_debuff_1",
    "condition_label": "(1)",
    "denko_id": "extra:008",
    "effect_kind": "def_debuff",
    "name": "阿下喜ケイ",
    "reasons": [
      "condition_effect_mismatch_needs_review"
    ],
    "reasons_zh": [
      "日文效果词与组件类型矛盾"
    ]
  },
  {
    "component_id": "hp_recovery_1",
    "condition_label": "(1)",
    "denko_id": "extra:011",
    "effect_kind": "hp_recovery",
    "name": "木屋はかり",
    "reasons": [
      "labeled_component_count_mismatch"
    ],
    "reasons_zh": [
      "编号标签与组件不匹配"
    ]
  },
  {
    "component_id": "duration_extension_3",
    "condition_label": "(3)",
    "denko_id": "extra:011",
    "effect_kind": "duration_extension",
    "name": "木屋はかり",
    "reasons": [
      "labeled_component_count_mismatch"
    ],
    "reasons_zh": [
      "编号标签与组件不匹配"
    ]
  },
  {
    "component_id": "exp_gain_1",
    "condition_label": "(1)",
    "denko_id": "extra:013",
    "effect_kind": "exp_gain",
    "name": "花形ひかる",
    "reasons": [
      "labeled_component_count_mismatch"
    ],
    "reasons_zh": [
      "编号标签与组件不匹配"
    ]
  },
  {
    "component_id": "atk_buff_1",
    "condition_label": "(1)",
    "denko_id": "extra:016",
    "effect_kind": "atk_buff",
    "name": "天台ヤコ",
    "reasons": [
      "condition_effect_mismatch_needs_review",
      "labeled_component_count_mismatch"
    ],
    "reasons_zh": [
      "日文效果词与组件类型矛盾",
      "编号标签与组件不匹配"
    ]
  },
  {
    "component_id": "def_buff_1",
    "condition_label": "(1)",
    "denko_id": "extra:016",
    "effect_kind": "def_buff",
    "name": "天台ヤコ",
    "reasons": [
      "condition_effect_mismatch_needs_review",
      "labeled_component_count_mismatch"
    ],
    "reasons_zh": [
      "日文效果词与组件类型矛盾",
      "编号标签与组件不匹配"
    ]
  },
  {
    "component_id": "score_gain",
    "condition_label": null,
    "denko_id": "extra:016",
    "effect_kind": "score_gain",
    "name": "天台ヤコ",
    "reasons": [
      "labeled_component_count_mismatch"
    ],
    "reasons_zh": [
      "编号标签与组件不匹配"
    ]
  },
  {
    "component_id": "extra_access",
    "condition_label": null,
    "denko_id": "extra:020",
    "effect_kind": "extra_access",
    "name": "エステル・サラ・パンクラス",
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
    "component_id": "atk_buff_1",
    "condition_label": "(1)",
    "denko_id": "extra:021",
    "effect_kind": "atk_buff",
    "name": "アンナ・チェルトナム",
    "reasons": [
      "labeled_component_count_mismatch"
    ],
    "reasons_zh": [
      "编号标签与组件不匹配"
    ]
  },
  {
    "component_id": "atk_buff_1",
    "condition_label": "(1)",
    "denko_id": "extra:028",
    "effect_kind": "atk_buff",
    "name": "ロン・リンファ",
    "reasons": [
      "labeled_component_count_mismatch"
    ],
    "reasons_zh": [
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