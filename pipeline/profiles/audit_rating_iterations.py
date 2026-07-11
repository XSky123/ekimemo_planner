from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
AUDITS = ROOT / "data/audits"
RATINGS = ROOT / "data/role_profiles/denko_ratings.jsonl"
OUT = AUDITS / "step3_rating_iteration_audit.json"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    issues: list[str] = []
    iterations = []
    for number in range(1, 6):
        summary_path = AUDITS / f"step3_rating_iteration_{number}_summary.json"
        reviews_path = AUDITS / f"step3_rating_iteration_{number}_reviews.jsonl"
        decision_path = AUDITS / f"step3_rating_iteration_{number}_decisions.json"
        if not all(path.exists() for path in (summary_path, reviews_path, decision_path)):
            issues.append(f"iteration_{number}:missing_artifact")
            continue
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        reviews = read_jsonl(reviews_path)
        decision = json.loads(decision_path.read_text(encoding="utf-8"))
        if len(reviews) != summary["selected"]:
            issues.append(f"iteration_{number}:selected_count_mismatch")
        if summary["cache_hits"] + summary["cache_misses"] != summary["selected"]:
            issues.append(f"iteration_{number}:cache_count_mismatch")
        if any(not (item.get("llm_review") or {}).get("review_zh") for item in reviews):
            issues.append(f"iteration_{number}:missing_review")
        if not (decision.get("db_backfill") or {}).get("decision"):
            issues.append(f"iteration_{number}:missing_db_decision")
        iterations.append({
            "iteration": number, "roles": summary["roles"], "selected": summary["selected"],
            "wiki_mismatches": summary["wiki_mismatches"], "cache_hits": summary["cache_hits"],
            "cache_misses": summary["cache_misses"], "db_decision": decision["db_backfill"]["decision"],
        })

    current = read_jsonl(AUDITS / "step3_rating_iteration_5_reviews.jsonl")
    ratings = read_jsonl(RATINGS)
    expected_mismatches = {row["rating_id"] for row in ratings if row["calibration"].get("status") == "mismatch"}
    reviewed_mismatches = {item["denko_id"] for item in current if "wiki_mismatch" in item["llm_review"]["selected_by"]}
    if expected_mismatches != reviewed_mismatches:
        issues.append("iteration_5:wiki_mismatch_coverage")
    labels = Counter(label for item in current for label in item["llm_review"]["selected_by"])
    for role in ("attack", "defense", "support", "expedition", "growth", "mechanism"):
        for band in ("top15", "bottom15"):
            if labels[f"{role}:{band}"] != 15:
                issues.append(f"iteration_5:{role}:{band}:coverage_{labels[f'{role}:{band}']}")

    report = (ROOT / "data/reports/step3_denko_ratings_zh.html").read_text(encoding="utf-8")
    checks = {
        "five_iterations_present": len(iterations) == 5,
        "iteration_5_all_wiki_mismatches_reviewed": expected_mismatches == reviewed_mismatches,
        "iteration_5_all_role_extremes_reviewed": all(labels[f"{role}:{band}"] == 15 for role in ("attack", "defense", "support", "expedition", "growth", "mechanism") for band in ("top15", "bottom15")),
        "report_has_one_line_recommendation": "一句话推荐" in report,
        "report_hides_review_process": all(token not in report for token in ("review_method", "cache_hit", "R1 ", "R2 ", "模型原始分")),
    }
    if not all(checks.values()):
        issues.append("final_contract_failed")
    result = {"artifact": "step3_rating_iteration_audit", "iterations": iterations, "checks": checks, "issue_count": len(issues), "issues": issues}
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
