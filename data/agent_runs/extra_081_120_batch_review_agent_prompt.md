# Batch Review Agent Task

Use `.agents/batch_review_expert.md` as the role prompt.

请复查本批 ingestion 结果，输出中文报告。重点看高风险项，不要读取全库或整页 wiki。

## Paths

- report: `data\reports\extra_081_120_batch_review_zh.html`
- skill_facts: `data/records/extra_081_120_skill_facts.jsonl`
- denko_facts: `data/records/extra_081_120_denko_facts.jsonl`
- review_queue: `data/review_queue/extra_081_120_review_queue.jsonl`

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
    "component_id": "score_gain",
    "condition_label": null,
    "denko_id": "extra:081",
    "effect_kind": "score_gain",
    "name": "ロッサ・ローマ",
    "reasons": [
      "condition_effect_mismatch_needs_review"
    ],
    "reasons_zh": [
      "日文效果词与组件类型矛盾"
    ]
  },
  {
    "component_id": "def_buff_1",
    "condition_label": "(1)",
    "denko_id": "extra:084",
    "effect_kind": "def_buff",
    "name": "ネラ・クライストチャーチ",
    "reasons": [
      "duplicate_labeled_component_values_need_review"
    ],
    "reasons_zh": [
      "多个编号组件值重复，疑似错位"
    ]
  },
  {
    "component_id": "def_buff_2",
    "condition_label": "(2)",
    "denko_id": "extra:084",
    "effect_kind": "def_buff",
    "name": "ネラ・クライストチャーチ",
    "reasons": [
      "duplicate_labeled_component_values_need_review"
    ],
    "reasons_zh": [
      "多个编号组件值重复，疑似错位"
    ]
  },
  {
    "component_id": "score_gain_1",
    "condition_label": "(1)",
    "denko_id": "extra:090",
    "effect_kind": "score_gain",
    "name": "キャシー・ナイアガラ",
    "reasons": [
      "labeled_component_count_mismatch"
    ],
    "reasons_zh": [
      "编号标签与组件不匹配"
    ]
  },
  {
    "component_id": "score_gain_1",
    "condition_label": "(1)",
    "denko_id": "extra:091",
    "effect_kind": "score_gain",
    "name": "ルーシー・ユニオン",
    "reasons": [
      "labeled_component_count_mismatch"
    ],
    "reasons_zh": [
      "编号标签与组件不匹配"
    ]
  },
  {
    "component_id": "exp_gain_2",
    "condition_label": "(2)",
    "denko_id": "extra:110",
    "effect_kind": "exp_gain",
    "name": "ヨンサン・ソウ",
    "reasons": [
      "duplicate_labeled_component_values_need_review"
    ],
    "reasons_zh": [
      "多个编号组件值重复，疑似错位"
    ]
  },
  {
    "component_id": "exp_gain_3",
    "condition_label": "(3)",
    "denko_id": "extra:110",
    "effect_kind": "exp_gain",
    "name": "ヨンサン・ソウ",
    "reasons": [
      "duplicate_labeled_component_values_need_review"
    ],
    "reasons_zh": [
      "多个编号组件值重复，疑似错位"
    ]
  },
  {
    "component_id": "exp_gain_2",
    "condition_label": "(2)",
    "denko_id": "extra:111",
    "effect_kind": "exp_gain",
    "name": "トンタン・チェリン",
    "reasons": [
      "duplicate_labeled_component_values_need_review"
    ],
    "reasons_zh": [
      "多个编号组件值重复，疑似错位"
    ]
  },
  {
    "component_id": "exp_gain_3",
    "condition_label": "(3)",
    "denko_id": "extra:111",
    "effect_kind": "exp_gain",
    "name": "トンタン・チェリン",
    "reasons": [
      "duplicate_labeled_component_values_need_review"
    ],
    "reasons_zh": [
      "多个编号组件值重复，疑似错位"
    ]
  },
  {
    "component_id": "exp_gain_2",
    "condition_label": "(2)",
    "denko_id": "extra:112",
    "effect_kind": "exp_gain",
    "name": "ソウル・マウム",
    "reasons": [
      "duplicate_labeled_component_values_need_review"
    ],
    "reasons_zh": [
      "多个编号组件值重复，疑似错位"
    ]
  },
  {
    "component_id": "exp_gain_3",
    "condition_label": "(3)",
    "denko_id": "extra:112",
    "effect_kind": "exp_gain",
    "name": "ソウル・マウム",
    "reasons": [
      "duplicate_labeled_component_values_need_review"
    ],
    "reasons_zh": [
      "多个编号组件值重复，疑似错位"
    ]
  },
  {
    "component_id": "def_buff_1",
    "condition_label": "(1)",
    "denko_id": "extra:118",
    "effect_kind": "def_buff",
    "name": "リーガ・イマンタ",
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
    "denko_id": "extra:119",
    "effect_kind": "atk_buff",
    "name": "アニカ・タルトゥ",
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
    "denko_id": "extra:120",
    "effect_kind": "exp_gain",
    "name": "マルティナ・ヴィリニュス",
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