from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AUDITS = ROOT / "data/audits"
RATINGS = ROOT / "data/role_profiles/denko_ratings.jsonl"
REPORT = ROOT / "data/reports/step3_denko_ratings_zh.html"
OUT = AUDITS / "step3_player_rating_iteration_audit.json"
CATEGORIES = ("attack_front", "defense_front", "attack_support", "defense_support", "score_gain", "exp_gain")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    issues: list[str] = []
    iterations: list[dict[str, Any]] = []
    for number in range(1, 6):
        summary_path = AUDITS / f"step3_player_rating_iteration_{number}_summary.json"
        reviews_path = AUDITS / f"step3_player_rating_iteration_{number}_reviews.jsonl"
        decisions_path = AUDITS / f"step3_player_rating_iteration_{number}_decisions.json"
        if not all(path.exists() for path in (summary_path, reviews_path, decisions_path)):
            issues.append(f"iteration_{number}:missing_artifact")
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        reviews = read_jsonl(reviews_path)
        decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
        if len(reviews) != summary["selected"]:
            issues.append(f"iteration_{number}:review_count_mismatch")
        if summary["cache_hits"] + summary["cache_misses"] != summary["selected"]:
            issues.append(f"iteration_{number}:cache_count_mismatch")
        if any(not (item.get("llm_review") or {}).get("review_zh") for item in reviews):
            issues.append(f"iteration_{number}:missing_llm_review")
        if not (decisions.get("db_backfill") or {}).get("decision"):
            issues.append(f"iteration_{number}:missing_db_decision")
        iterations.append({
            "iteration": number, "selected": summary["selected"], "wiki_mismatches": summary["wiki_mismatches"],
            "cache_hits": summary["cache_hits"], "cache_misses": summary["cache_misses"],
            "db_decision": decisions["db_backfill"]["decision"],
        })

    ratings = read_jsonl(RATINGS)
    final_reviews = read_jsonl(AUDITS / "step3_player_rating_iteration_5_reviews.jsonl")
    labels = Counter(label for item in final_reviews for label in item["llm_review"]["selected_by"])
    current_mismatches = {row["rating_id"] for row in ratings if row["calibration"].get("status") == "mismatch"}
    reviewed_mismatches = {item["denko_id"] for item in final_reviews if "wiki_mismatch" in item["llm_review"]["selected_by"]}
    if current_mismatches != reviewed_mismatches:
        issues.append("final_wiki_mismatch_coverage_failed")
    for category in CATEGORIES:
        for band in ("top15", "bottom15"):
            if labels[f"{category}:{band}"] != 15:
                issues.append(f"final_{category}_{band}_coverage_failed")

    use_case_audit = json.loads((AUDITS / "step3_player_use_case_rating_audit.json").read_text(encoding="utf-8"))
    step1_validation = json.loads((ROOT / "data/step1_db/validation.json").read_text(encoding="utf-8"))
    report = REPORT.read_text(encoding="utf-8")
    checks = {
        "five_full_iterations_present": len(iterations) == 5,
        "final_all_wiki_mismatches_reviewed": current_mismatches == reviewed_mismatches,
        "final_all_category_extremes_reviewed": all(labels[f"{category}:{band}"] == 15 for category in CATEGORIES for band in ("top15", "bottom15")),
        "step1_validation_green": step1_validation["issue_count"] == 0,
        "use_case_audit_green": use_case_audit["issue_count"] == 0,
        "report_is_compact": all(label in report for label in ("用途分", "属性", "类型", "模型一句话推荐", "高价值配队观测", "Wiki评价", "Wiki评语", "博客评价", "博客评语")),
        "report_has_no_overall_or_process": all(token not in report for token in (">总评<", "按总分", "cache_hit", "review_method", "R1 ", "R2 ")),
    }
    if not all(checks.values()):
        issues.append("final_contract_failed")
    result = {
        "artifact": "step3_player_rating_iteration_audit", "iterations": iterations,
        "checks": checks, "final_selection_labels": dict(sorted(labels.items())),
        "issue_count": len(issues), "issues": sorted(set(issues)),
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
