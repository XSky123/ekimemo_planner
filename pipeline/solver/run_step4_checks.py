from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline.solver import test_solver_regressions  # noqa: E402
from pipeline.solver.solve_team import HANDLED_FILTER_KEYS, SCENE_EFFECTS, read_json, read_jsonl, solve  # noqa: E402


PROFILES = ROOT / "data" / "role_profiles" / "role_profiles.jsonl"
EXAMPLES = ROOT / "data" / "solver_examples"
AUDIT = ROOT / "data" / "audits" / "step4_solver_audit.json"
TMP_RESULTS = ROOT / "tmp" / "solver_examples"
REPORT = ROOT / "data" / "reports" / "step4_solver_examples_zh.html"


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def profile_constraint_audit(profiles: list[dict[str, Any]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for profile in profiles:
        component = profile["component"]
        filters = component.get("target_filters") or {}
        recipients = set(component.get("recipient") or [])
        condition = str(component.get("source", {}).get("condition_raw") or "")
        profile_id = profile["profile_id"]
        if "own_access_attribute" in filters and not (recipients & {"accessing_denko", "team_all", "own_team", "opponent_denko", "opponent_team"}):
            issues.append({"profile_id": profile_id, "reason_zh": "访问者属性限制没有可解释的受益对象"})
        if "station_attribute" in filters and "駅" not in condition:
            issues.append({"profile_id": profile_id, "reason_zh": "站点属性字段缺少站点原文证据"})
        if "own_access_attribute" in filters and "station_attribute" not in filters and "駅" in condition:
            issues.append({"profile_id": profile_id, "reason_zh": "访问者属性条件可能遗漏站点属性限制"})
        own_side_debuff = component.get("effect_kind") in {"atk_debuff", "def_debuff", "ap_debuff"} and bool(recipients & {"self", "team_all", "own_team"})
        if own_side_debuff:
            costs = set(profile.get("constraints", {}).get("opportunity_costs") or [])
            scenes = {item.get("id") for item in profile.get("scene_tags") or []}
            if "self_debuff" not in costs:
                issues.append({"profile_id": profile_id, "reason_zh": "己方能力下降未标记为自损代价"})
            if scenes & {"capture", "defense"}:
                issues.append({"profile_id": profile_id, "reason_zh": "己方能力下降错误进入突破或守站场景"})
    return issues


def unmodeled_condition_coverage(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Persistent controller feedback: condition types to model before broadening results."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for profile in profiles:
        filters = profile["component"].get("target_filters") or {}
        for key, value in filters.items():
            if key in HANDLED_FILTER_KEYS or value in (None, "", False, [], {}):
                continue
            grouped[key].append(profile)
    result = []
    for key, affected in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0])):
        scenes = Counter(
            scene
            for profile in affected
            for scene, kinds in SCENE_EFFECTS.items()
            if profile["component"].get("effect_kind") in kinds
        )
        result.append({
            "condition_key": key,
            "affected_components": len(affected),
            "scene_counts": dict(sorted(scenes.items())),
            "priority": "high" if len(affected) >= 10 or bool({"capture", "defense"} & set(scenes)) else "medium",
            "sample_profile_ids": [profile["profile_id"] for profile in affected[:5]],
        })
    return result


def example_audit() -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    summaries: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    for path in sorted(EXAMPLES.glob("*.json")):
        try:
            result = solve(read_json(path))
            summaries.append({
                "request": path.name,
                "teams": len(result["teams"]),
                "active_components": sum(len(team["active_components"]) for team in result["teams"]),
                "pending_components": sum(team["constraints_check"]["inactive_or_pending_count"] for team in result["teams"]),
            })
        except Exception as exc:  # surfaced in the persistent audit artifact
            issues.append({"request": path.name, "reason_zh": f"示例求解失败：{exc}"})
    return summaries, issues


def rebuild_example_report() -> list[dict[str, str]]:
    """The report is generated from fresh results, never hand-edited."""
    TMP_RESULTS.mkdir(parents=True, exist_ok=True)
    sources = [
        EXAMPLES / "capture_original_026_lv50.json",
        EXAMPLES / "defense_original_001_lv50.json",
        EXAMPLES / "mechanism_extra_107_lv50.json",
    ]
    result_paths: list[Path] = []
    issues: list[dict[str, str]] = []
    for source in sources:
        if not source.exists():
            issues.append({"request": source.name, "reason_zh": "报告样例请求不存在"})
            continue
        output = TMP_RESULTS / source.name
        write_json(output, solve(read_json(source)))
        result_paths.append(output)
    if issues:
        return issues
    command = [sys.executable, "pipeline/solver/write_solver_report.py", *(str(path) for path in result_paths), "--output", str(REPORT)]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if completed.returncode:
        issues.append({"request": "step4_solver_examples_zh.html", "reason_zh": f"报告构建失败：{completed.stderr.strip() or completed.stdout.strip()}"})
        return issues
    text = REPORT.read_text(encoding="utf-8") if REPORT.exists() else ""
    if "Step4 配队求解样例" not in text or "返回报告目录" not in text or "???" in text:
        issues.append({"request": "step4_solver_examples_zh.html", "reason_zh": "报告静态内容或编码检查失败"})
    return issues


def main() -> int:
    profiles = read_jsonl(PROFILES)
    constraint_issues = profile_constraint_audit(profiles)
    coverage = unmodeled_condition_coverage(profiles)
    regression_status = test_solver_regressions.main()
    examples, example_issues = example_audit()
    report_issues = rebuild_example_report()
    result = {
        "artifact": "step4_solver_audit",
        "profiles": len(profiles),
        "regression_exit_code": regression_status,
        "constraint_issue_count": len(constraint_issues),
        "constraint_issues": constraint_issues,
        "unmodeled_condition_coverage": coverage,
        "unmodeled_condition_type_count": len(coverage),
        "coverage_policy_zh": "未建模的限制必须保持 pending_context，不能默认计入数值；此列表是自动扩展规则与回归测试的候选队列。",
        "examples": examples,
        "example_issue_count": len(example_issues),
        "example_issues": example_issues,
        "report_issue_count": len(report_issues),
        "report_issues": report_issues,
        "issue_count": len(constraint_issues) + len(example_issues) + len(report_issues) + (1 if regression_status else 0),
    }
    write_json(AUDIT, result)
    print(json.dumps({"profiles": len(profiles), "issue_count": result["issue_count"], "examples": len(examples)}, ensure_ascii=True))
    return 1 if result["issue_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
