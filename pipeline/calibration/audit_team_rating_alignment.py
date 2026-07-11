from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CALIBRATION = ROOT / "data/observed_cases/team_calibration.json"
RATINGS = ROOT / "data/role_profiles/denko_ratings.jsonl"
BLOG = ROOT / "data/reference_priors/blog_character_ratings.json"
DENKO = ROOT / "data/step1_db/denko_facts.jsonl"
REPORT = ROOT / "data/reports/step3_denko_ratings_zh.html"
OUT = ROOT / "data/audits/step3_team_rating_alignment_audit.json"
CATEGORIES = ("attack_front", "defense_front", "attack_support", "defense_support", "score_gain", "exp_gain")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    calibration = json.loads(CALIBRATION.read_text(encoding="utf-8"))
    ratings = read_jsonl(RATINGS)
    by_id = {row["rating_id"]: row for row in ratings}
    ranking = {
        category: {
            row["rating_id"]: index
            for index, row in enumerate(sorted(ratings, key=lambda item: (-item["levels"]["80"]["role_scores"][category], item["rating_id"])), 1)
        }
        for category in CATEGORIES
    }
    comparisons: list[dict[str, Any]] = []
    severe_mismatches: list[dict[str, Any]] = []
    observed_without_direct_capability: list[dict[str, Any]] = []
    for denko_id, usage in (calibration.get("denko_usage") or {}).items():
        if denko_id not in by_id:
            continue
        for category, signal in (usage.get("use_case_signals") or {}).items():
            if category not in CATEGORIES or signal <= 0:
                continue
            result = by_id[denko_id]["levels"]["80"]
            item = {
                "denko_id": denko_id, "category": category, "observed_weight": signal,
                "rank": ranking[category][denko_id], "score": result["role_scores"][category],
                "fact_model_score": result["model_role_scores"][category],
                "team_ids": usage.get("team_ids") or [],
            }
            comparisons.append(item)
            if result["model_role_scores"][category] == 0:
                observed_without_direct_capability.append(item)
            if signal >= 1.0 and result["model_role_scores"][category] > 0:
                leader_weight = float(usage.get("weighted_leader_appearances") or 0)
                if category in {"attack_front", "defense_front"} and leader_weight >= 1.0 and item["rank"] > 25:
                    severe_mismatches.append(item)
                elif category in {"attack_support", "defense_support"} and item["score"] < 45:
                    severe_mismatches.append(item)
                elif category in {"score_gain", "exp_gain"} and item["rank"] > 50:
                    severe_mismatches.append(item)
    named = {
        denko_id: {
            "rank_lv80_attack_front": ranking["attack_front"][denko_id],
            "score_lv80_attack_front": by_id[denko_id]["levels"]["80"]["role_scores"]["attack_front"],
            "observed_weight": (calibration["denko_usage"].get(denko_id) or {}).get("use_case_signals", {}).get("attack_front", 0),
        }
        for denko_id in ("original:030", "original:072", "original:059")
    }
    blog = json.loads(BLOG.read_text(encoding="utf-8"))
    blog_by_id = {item["denko_id"]: item for item in blog.get("ratings") or []}
    canonical_ids = {
        str((row.get("identity") or {}).get("denko_id") or row.get("denko_id"))
        for row in read_jsonl(DENKO)
    }
    blog_identity_issues = [
        {"denko_id": item.get("denko_id"), "name_ja": item.get("name_ja"), "reason": "unknown_denko_id"}
        for item in blog.get("ratings") or []
        if item.get("denko_id") not in canonical_ids
    ]
    report = REPORT.read_text(encoding="utf-8")
    checks = {
        "team_archive_parsed": calibration["counts"]["teams"] >= 15 and calibration["counts"]["resolved_denko"] >= 40,
        "no_severe_observed_model_mismatches": not severe_mismatches,
        "reno_high": named["original:030"]["rank_lv80_attack_front"] <= 5,
        "nagisa_visible": named["original:072"]["rank_lv80_attack_front"] <= 20,
        "momiji_high": named["original:059"]["rank_lv80_attack_front"] <= 15,
        "named_blog_ratings_present": all(denko_id in blog_by_id for denko_id in ("original:030", "original:072", "original:059", "original:087")),
        "blog_ids_resolve_to_step1": not blog_identity_issues and len(blog_by_id) == blog["counts"]["ratings"],
        "report_separates_evidence": all(label in report for label in ("模型一句话推荐", "高价值配队观测", "Wiki评价", "Wiki评语", "博客评价", "博客评语")),
        "report_hides_generic_review": ">核查评语<" not in report,
    }
    issues = [key for key, passed in checks.items() if not passed]
    result = {
        "artifact": "step3_team_rating_alignment_audit", "source": calibration["source"],
        "counts": {
            "comparisons": len(comparisons),
            "severe_mismatches": len(severe_mismatches),
            "observed_without_direct_capability": len(observed_without_direct_capability),
            "blog_ratings": len(blog_by_id),
            "blog_identity_issues": len(blog_identity_issues),
        },
        "checks": checks, "named": named, "severe_mismatches": severe_mismatches,
        "observed_without_direct_capability": observed_without_direct_capability,
        "blog_identity_issues": blog_identity_issues,
        "top_observed_comparisons": sorted(comparisons, key=lambda item: (-item["observed_weight"], item["rank"]))[:30],
        "issue_count": len(issues), "issues": issues,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"checks": checks, "counts": result["counts"], "named": named, "issue_count": len(issues)}, ensure_ascii=False))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
