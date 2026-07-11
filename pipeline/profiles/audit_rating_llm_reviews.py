from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/audits/step3_rating_llm_two_round_audit.json"
SCENES = {"daily_attack", "burst_attack", "home_defense", "expedition_score", "expedition_exp", "growth", "mechanism"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    issues = []
    rounds = []
    for round_number in (1, 2):
        path = ROOT / "data/audits" / f"step3_rating_llm_round{round_number}.jsonl"
        rows = read_jsonl(path)
        counts = Counter((row["scene"], row["band"]) for row in rows)
        expected = {(scene, band): 15 for scene in SCENES for band in ("top", "bottom")}
        if counts != expected:
            issues.append(f"round{round_number}:sample_shape_mismatch")
        if any(not row.get("components") for row in rows):
            issues.append(f"round{round_number}:empty_scene_candidate")
        if any(not (row.get("llm_review") or {}).get("reviewed") for row in rows):
            issues.append(f"round{round_number}:unreviewed_row")
        verdicts = Counter(row["llm_review"]["verdict"] for row in rows)
        layers = Counter(row["llm_review"]["layer"] for row in rows if row["llm_review"]["action"] != "none")
        rounds.append({
            "round": round_number, "rows": len(rows), "reviewed": sum(row["llm_review"]["reviewed"] for row in rows),
            "by_verdict": dict(sorted(verdicts.items())), "actionable_by_layer": dict(sorted(layers.items())),
        })
    rating_audit = json.loads((ROOT / "data/audits/step3_denko_rating_audit.json").read_text(encoding="utf-8"))
    schema_audit = json.loads((ROOT / "data/audits/step3_denko_rating_schema_audit.json").read_text(encoding="utf-8"))
    profile_validation = json.loads((ROOT / "data/role_profiles/validation.json").read_text(encoding="utf-8"))
    report = (ROOT / "data/reports/step3_denko_ratings_zh.html").read_text(encoding="utf-8")
    final_checks = {
        "rating_issue_count": rating_audit["issue_count"],
        "rating_schema_issue_count": schema_audit["issue_count"],
        "profile_issue_count": profile_validation["issue_count"],
        "one_line_recommendations_present": rating_audit["checks"].get("one_line_recommendations_present"),
        "report_hides_review_process_metadata": all(token not in report for token in ("R1 ", "R2 ", "模型原始分", "处理：")),
        "report_has_review_comments": "峰值" in report or "门槛" in report or "条件" in report,
        "report_is_compact_use_case_lookup": all(label in report for label in ("攻击车头", "守站肉盾", "攻击队友", "防守队友", "加分", "加经验", "一句话推荐")),
        "report_has_attribute_type_filters": all(token in report for token in ('id="attribute"', 'id="type"')),
        "report_hides_step2_detail_columns": all(label not in report for label in (">概率<", ">覆盖<", ">启动条件<", ">范围 / 代价<")),
        "report_has_no_published_overall": ">总评<" not in report and "按总分排序" not in report,
    }
    if not all(value == 0 for key, value in final_checks.items() if key.endswith("issue_count")):
        issues.append("final_generated_audit_not_green")
    if not all(value for key, value in final_checks.items() if not key.endswith("issue_count")):
        issues.append("final_report_contract_failed")
    result = {
        "artifact": "step3_rating_llm_two_round_audit", "rounds": rounds,
        "review_instances": sum(row["reviewed"] for row in rounds),
        "final_checks": final_checks, "issue_count": len(issues), "issues": issues,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
