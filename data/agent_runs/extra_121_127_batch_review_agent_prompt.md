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
[]
```

## Required Output

- batch
- priority_findings
- random_sample_findings
- common_patterns_to_fix
- manual_fill_candidates
- do_not_fix_in_parser_yet