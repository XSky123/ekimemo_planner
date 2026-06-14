# Batch Review Agent Task

Use `.agents/batch_review_expert.md` as the role prompt.

请复查本批 ingestion 结果，输出中文报告。重点看高风险项，不要读取全库或整页 wiki。

## Paths

- report: `data\reports\extra_041_080_batch_review_zh.html`
- skill_facts: `data/records/extra_041_080_skill_facts.jsonl`
- denko_facts: `data/records/extra_041_080_denko_facts.jsonl`
- review_queue: `data/review_queue/extra_041_080_review_queue.jsonl`

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
    "component_id": "reboot_2",
    "condition_label": "(2)",
    "denko_id": "extra:041",
    "effect_kind": "reboot",
    "name": "レニャ・サンモリッツ",
    "reasons": [
      "vu_label_level_mismatch_needs_review"
    ],
    "reasons_zh": [
      "原文声明该编号 Lv92+ 生效，但组件等级不是 VU-only"
    ]
  },
  {
    "component_id": "component_01_exp_gain",
    "condition_label": null,
    "denko_id": "extra:046",
    "effect_kind": "exp_gain",
    "name": "五葉あこ",
    "reasons": [
      "component_values_not_parsed"
    ],
    "reasons_zh": [
      "组件值未解析"
    ]
  },
  {
    "component_id": "atk_buff_3",
    "condition_label": "(3)",
    "denko_id": "extra:048",
    "effect_kind": "atk_buff",
    "name": "エマ・ノアイユ",
    "reasons": [
      "labeled_component_count_mismatch"
    ],
    "reasons_zh": [
      "编号标签与组件不匹配"
    ]
  },
  {
    "component_id": "def_buff_1",
    "condition_label": "(1)",
    "denko_id": "extra:058",
    "effect_kind": "def_buff",
    "name": "ピン・ユートン",
    "reasons": [
      "labeled_component_count_mismatch"
    ],
    "reasons_zh": [
      "编号标签与组件不匹配"
    ]
  },
  {
    "component_id": "hp_recovery",
    "condition_label": null,
    "denko_id": "extra:058",
    "effect_kind": "hp_recovery",
    "name": "ピン・ユートン",
    "reasons": [
      "labeled_component_count_mismatch"
    ],
    "reasons_zh": [
      "编号标签与组件不匹配"
    ]
  },
  {
    "component_id": "damage_reduction_2",
    "condition_label": "(2)",
    "denko_id": "extra:062",
    "effect_kind": "damage_reduction",
    "name": "笛吹エイル",
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
    "component_id": "damage_reduction_3",
    "condition_label": "(3)",
    "denko_id": "extra:062",
    "effect_kind": "damage_reduction",
    "name": "笛吹エイル",
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
    "denko_id": "extra:067",
    "effect_kind": "atk_buff",
    "name": "エドウィナ・プレトリア",
    "reasons": [
      "labeled_component_count_mismatch"
    ],
    "reasons_zh": [
      "编号标签与组件不匹配"
    ]
  },
  {
    "component_id": "score_gain",
    "condition_label": null,
    "denko_id": "extra:068",
    "effect_kind": "score_gain",
    "name": "アダリヤ・ビクトリア",
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
    "denko_id": "extra:073",
    "effect_kind": "def_debuff",
    "name": "アチャラ・メークローン",
    "reasons": [
      "condition_effect_mismatch_needs_review"
    ],
    "reasons_zh": [
      "日文效果词与组件类型矛盾"
    ]
  },
  {
    "component_id": "reboot_3",
    "condition_label": "(3)",
    "denko_id": "extra:073",
    "effect_kind": "reboot",
    "name": "アチャラ・メークローン",
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