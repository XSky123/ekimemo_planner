from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import parse as base
import original_range_ingest as range_ingest


AGENT_RUN_DIR = base.ROOT / "data" / "agent_runs"

BLOCKING_REASONS = {
    "component_values_not_parsed",
    "key_level_component_missing",
    "labeled_component_count_mismatch",
    "compound_labeled_effect_needs_manual_review",
    "duplicate_labeled_component_values_need_review",
    "condition_effect_mismatch_needs_review",
    "attribute_branch_effect_needs_review",
    "primary_labeled_effect_vu_only_needs_review",
    "vu_label_level_mismatch_needs_review",
}

REASON_ZH = {
    "component_values_not_parsed": "组件值未解析",
    "key_level_component_missing": "关键等级缺值",
    "labeled_component_count_mismatch": "编号标签与组件不匹配",
    "compound_labeled_effect_needs_manual_review": "复合编号需要片段复查",
    "duplicate_labeled_component_values_need_review": "多个编号组件值重复，疑似错位",
    "condition_effect_mismatch_needs_review": "日文效果词与组件类型矛盾",
    "attribute_branch_effect_needs_review": "属性分支需要复查",
    "primary_labeled_effect_vu_only_needs_review": "(1) 主效果仅 VU 生效，疑似解析错位",
    "vu_label_level_mismatch_needs_review": "原文声明该编号 Lv92+ 生效，但组件等级不是 VU-only",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def run_ingestion(start: int, end: int, batch_size: int) -> dict[str, Any]:
    command = [
        sys.executable,
        str(Path(__file__).with_name("original_range_ingest.py")),
        "--start",
        str(start),
        "--end",
        str(end),
        "--batch-size",
        str(batch_size),
    ]
    completed = subprocess.run(command, cwd=base.ROOT, text=True, capture_output=True, check=False)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def component_reason_counts(skill_rows: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in skill_rows:
        for component in row.get("skill_components") or []:
            counts.update(component.get("review_reasons") or [])
    return counts


def blocking_items(skill_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for row in skill_rows:
        for component in row.get("skill_components") or []:
            reasons = sorted(set(component.get("review_reasons") or []) & BLOCKING_REASONS)
            if not reasons:
                continue
            items.append(
                {
                    "denko_id": row.get("denko_id"),
                    "name": row.get("name"),
                    "component_id": component.get("component_id"),
                    "effect_kind": component.get("effect_kind"),
                    "condition_label": component.get("condition_label"),
                    "reasons": reasons,
                    "reasons_zh": [REASON_ZH.get(reason, reason) for reason in reasons],
                }
            )
    return items


def relevant_observed_cases(stem: str) -> list[str]:
    observed_dir = base.ROOT / "data" / "observed_cases"
    if not observed_dir.exists():
        return []
    paths = list(observed_dir.glob("*parser_*.jsonl")) + list(observed_dir.glob("*review_rules*.jsonl"))
    return [
        str(path.relative_to(base.ROOT))
        for path in sorted(set(paths))
        if stem in path.name
        or "original_080_119" in path.name
        or "original_120_163" in path.name
        or "review_rules" in path.name
    ]


def write_batch_review_prompt(stem: str, state: dict[str, Any]) -> Path:
    prompt_path = AGENT_RUN_DIR / f"{stem}_batch_review_agent_prompt.md"
    lines = [
        "# Batch Review Agent Task",
        "",
        "Use `.agents/batch_review_expert.md` as the role prompt.",
        "",
        "请复查本批 ingestion 结果，输出中文报告。重点看高风险项，不要读取全库或整页 wiki。",
        "",
        "## Paths",
        "",
        f"- report: `{state['paths']['report']}`",
        f"- skill_facts: `{state['paths']['skill_facts']}`",
        f"- denko_facts: `{state['paths']['denko_facts']}`",
        f"- review_queue: `{state['paths']['review_queue']}`",
        "",
        "## Observed Cases",
        "",
    ]
    for path in state["paths"]["observed_cases"]:
        lines.append(f"- `{path}`")
    lines.extend(
        [
            "",
            "## Blocking Items",
            "",
            "优先确认这些是否是 parser 共性问题、manual fill、还是报告误报：",
            "",
            "```json",
            json.dumps(state["blocking_items"][:80], ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
            "## Required Output",
            "",
            "- batch",
            "- priority_findings",
            "- random_sample_findings",
            "- common_patterns_to_fix",
            "- manual_fill_candidates",
            "- do_not_fix_in_parser_yet",
        ]
    )
    prompt_path.write_text("\n".join(lines), encoding="utf-8")
    return prompt_path


def build_state(start: int, end: int, batch_size: int, run_result: dict[str, Any] | None) -> dict[str, Any]:
    stem = range_ingest.output_stem(start, end)
    paths = {
        "report": f"data/reports/{stem}_batch_review_zh.html",
        "skill_facts": f"data/records/{stem}_skill_facts.jsonl",
        "denko_facts": f"data/records/{stem}_denko_facts.jsonl",
        "review_queue": f"data/review_queue/{stem}_review_queue.jsonl",
        "observed_cases": relevant_observed_cases(stem),
    }
    skill_rows = read_jsonl(base.ROOT / paths["skill_facts"])
    reason_counts = component_reason_counts(skill_rows)
    blockers = blocking_items(skill_rows)
    state = {
        "schema_version": 1,
        "generated_at": datetime.now(base.JST).isoformat(),
        "scope": {"pool": "original", "start": start, "end": end, "batch_size": batch_size},
        "parser_version": base.PARSER_VERSION,
        "run_result": run_result,
        "paths": paths,
        "metrics": {
            "skill_records": len(skill_rows),
            "component_review_reason_counts": dict(sorted(reason_counts.items())),
            "blocking_item_count": len(blockers),
        },
        "blocking_items": blockers,
        "next_action": "spawn_batch_review_expert" if blockers else "complete",
    }
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--batch-size", type=int, default=30)
    parser.add_argument("--no-run", action="store_true", help="Only summarize existing outputs.")
    args = parser.parse_args()

    AGENT_RUN_DIR.mkdir(parents=True, exist_ok=True)
    run_result = None if args.no_run else run_ingestion(args.start, args.end, args.batch_size)
    if run_result and run_result["returncode"] != 0:
        state = build_state(args.start, args.end, args.batch_size, run_result)
        state["next_action"] = "fix_ingestion_command"
        state_path = AGENT_RUN_DIR / f"{range_ingest.output_stem(args.start, args.end)}_cycle_state.json"
        write_json(state_path, state)
        print(json.dumps({"state": str(state_path.relative_to(base.ROOT)), "next_action": state["next_action"]}, ensure_ascii=False))
        return run_result["returncode"]

    state = build_state(args.start, args.end, args.batch_size, run_result)
    stem = range_ingest.output_stem(args.start, args.end)
    state_path = AGENT_RUN_DIR / f"{stem}_cycle_state.json"
    write_json(state_path, state)
    prompt_path = write_batch_review_prompt(stem, state)
    print(
        json.dumps(
            {
                "state": str(state_path.relative_to(base.ROOT)),
                "agent_prompt": str(prompt_path.relative_to(base.ROOT)),
                "next_action": state["next_action"],
                "blocking_item_count": state["metrics"]["blocking_item_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
