from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RATINGS = ROOT / "data/role_profiles/denko_ratings.jsonl"
CALIBRATION = ROOT / "data/observed_cases/team_calibration.json"
BLOG = ROOT / "data/reference_priors/blog_character_ratings.json"
ALIGNMENT = ROOT / "data/audits/step3_team_rating_alignment_audit.json"
CONDITIONS = ROOT / "data/audits/step3_scored_component_condition_audit.json"
REPORT = ROOT / "data/reports/step3_denko_ratings_zh.html"
OUT = ROOT / "data/audits/step3_observed_rating_stability_audit.json"
CATEGORIES = ("attack_front", "defense_front", "attack_support", "defense_support", "score_gain", "exp_gain")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def semantic_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def sample_record(row: dict[str, Any], category: str) -> dict[str, Any]:
    level = row["levels"]["80"]
    components = level["use_case_components"].get(category) or []
    scene_components = [
        component
        for scene in level.get("scenes", {}).values()
        for component in scene.get("top_components") or []
    ]
    stats = row.get("denko", {}).get("key_level_stats", {}).get("80") or {}
    intrinsic_front_stat = stats.get("AP") if category == "attack_front" else (stats.get("HP") if category == "defense_front" else None)
    return {
        "denko_id": row["rating_id"],
        "name": row["denko"].get("name"),
        "category": category,
        "score": level["role_scores"][category],
        "fact_model_score": level["model_role_scores"][category],
        "observed_signal": level["observed_use_case_signals"][category],
        "blog_bonus": level["blog_prior_bonuses"][category],
        "component_count": len(components),
        "component_hash": semantic_hash(components),
        "scene_component_count": len(scene_components),
        "scene_component_hash": semantic_hash(scene_components),
        "intrinsic_front_stat": intrinsic_front_stat,
    }


def take_unique(candidates: list[tuple[dict[str, Any], str]], count: int = 15) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row, category in candidates:
        key = (row["rating_id"], category)
        if key in seen:
            continue
        seen.add(key)
        result.append(sample_record(row, category))
        if len(result) == count:
            break
    return result


def validate_sample(sample: list[dict[str, Any]]) -> list[dict[str, Any]]:
    findings = []
    for item in sample:
        changed = item["score"] != item["fact_model_score"]
        has_prior = item["observed_signal"] > 0 or item["blog_bonus"] > 0
        if item["fact_model_score"] == 0 and item["score"] != 0:
            findings.append({**item, "reason": "prior_created_missing_capability"})
        elif changed and not has_prior:
            findings.append({**item, "reason": "score_changed_without_calibration_evidence"})
        elif item["score"] > 0 and item["component_count"] == 0:
            has_scene_or_stat_basis = item["scene_component_count"] > 0 or bool(item["intrinsic_front_stat"])
            if item["category"] not in {"attack_front", "defense_front"} or not has_scene_or_stat_basis:
                findings.append({**item, "reason": "positive_score_without_skill_scene_or_front_stat_basis"})
    return findings


def main() -> int:
    ratings = read_jsonl(RATINGS)
    alignment = json.loads(ALIGNMENT.read_text(encoding="utf-8"))
    conditions = json.loads(CONDITIONS.read_text(encoding="utf-8"))
    calibration = json.loads(CALIBRATION.read_text(encoding="utf-8"))
    blog = json.loads(BLOG.read_text(encoding="utf-8"))
    report = REPORT.read_text(encoding="utf-8")

    observed_candidates: list[tuple[dict[str, Any], str]] = []
    uplift_candidates: list[tuple[dict[str, Any], str]] = []
    boundary_candidates: list[tuple[dict[str, Any], str]] = []
    for category in CATEGORIES:
        eligible = [row for row in ratings if row["levels"]["80"]["role_scores"][category] > 0]
        ordered = sorted(eligible, key=lambda row: (-row["levels"]["80"]["role_scores"][category], row["rating_id"]))
        boundary_candidates.extend((row, category) for row in ordered[12:18])
        boundary_candidates.extend((row, category) for row in ordered[-3:])
        for row in eligible:
            level = row["levels"]["80"]
            if level["observed_use_case_signals"][category] > 0:
                observed_candidates.append((row, category))
            if level["role_scores"][category] > level["model_role_scores"][category]:
                uplift_candidates.append((row, category))

    observed_candidates.sort(key=lambda pair: (-pair[0]["levels"]["80"]["observed_use_case_signals"][pair[1]], pair[0]["rating_id"], pair[1]))
    uplift_candidates.sort(key=lambda pair: (-(pair[0]["levels"]["80"]["role_scores"][pair[1]] - pair[0]["levels"]["80"]["model_role_scores"][pair[1]]), pair[0]["rating_id"], pair[1]))
    boundary_candidates.sort(key=lambda pair: (pair[1], pair[0]["rating_id"]))
    cycles = [
        {"cycle": 1, "focus": "highest observed occurrence", "sample": take_unique(observed_candidates)},
        {"cycle": 2, "focus": "largest evidence-backed uplift", "sample": take_unique(uplift_candidates)},
        {"cycle": 3, "focus": "ranking boundary and low-score regression", "sample": take_unique(boundary_candidates)},
    ]
    for cycle in cycles:
        cycle["findings"] = validate_sample(cycle["sample"])
        cycle["sample_count"] = len(cycle["sample"])
        cycle["finding_count"] = len(cycle["findings"])

    checks = {
        "three_distinct_15_record_cycles": len(cycles) == 3 and all(item["sample_count"] == 15 for item in cycles),
        "sample_cycles_have_no_invariant_findings": all(not item["findings"] for item in cycles),
        "scored_condition_scan_clean": conditions.get("issue_count") == 0 and conditions.get("checked_components", 0) >= 300,
        "team_alignment_clean": alignment.get("issue_count") == 0 and alignment.get("counts", {}).get("comparisons", 0) >= 50,
        "archive_provenance_present": calibration.get("source", {}).get("archive_hash") and len(calibration.get("teams") or []) >= 15,
        "blog_provenance_present": blog.get("counts", {}).get("ratings", 0) >= 100 and len(blog.get("sources") or []) == 4,
        "report_evidence_layers_separate": all(label in report for label in ("模型一句话推荐", "高价值配队观测", "Wiki评价", "Wiki评语", "博客评价", "博客评语")),
    }
    issues = [key for key, passed in checks.items() if not passed]
    result = {
        "artifact": "step3_observed_rating_stability_audit",
        "method_zh": "连续三轮各抽取15个角色用途记录，分别覆盖高频配队、最大校准增幅、榜单边界与低分端；同时回归实际计分组件的结构化条件。",
        "cycles": cycles,
        "checks": checks,
        "issue_count": len(issues),
        "issues": issues,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"cycles": [{"cycle": item["cycle"], "samples": item["sample_count"], "findings": item["finding_count"]} for item in cycles], "checks": checks, "issue_count": len(issues)}, ensure_ascii=False))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
