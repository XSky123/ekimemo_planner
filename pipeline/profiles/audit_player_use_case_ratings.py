from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RATINGS = ROOT / "data/role_profiles/denko_ratings.jsonl"
REPORT = ROOT / "data/reports/step3_denko_ratings_zh.html"
OUT = ROOT / "data/audits/step3_player_use_case_rating_audit.json"
CATEGORIES = ("attack_front", "defense_front", "attack_support", "defense_support", "score_gain", "exp_gain")
TEAM_RECIPIENTS = {"team_all", "own_team", "own_front_car", "front_car", "relative_car", "accessing_denko", "accessed_denko"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def rank(rows: list[dict[str, Any]], denko_id: str, level: str, category: str) -> int:
    ordered = sorted(rows, key=lambda row: (-row["levels"][level]["role_scores"][category], row["rating_id"]))
    return next(index for index, row in enumerate(ordered, 1) if row["rating_id"] == denko_id)


def main() -> int:
    rows = read_jsonl(RATINGS)
    issues: list[str] = []
    distributions: dict[str, dict[str, Any]] = {}
    for level in ("50", "80"):
        for category in CATEGORIES:
            eligible = [row for row in rows if row["levels"][level]["use_case_raw"][category] > 0]
            ordered = sorted(eligible, key=lambda row: row["levels"][level]["use_case_raw"][category])
            raw_score_pairs = [
                (row["levels"][level]["use_case_raw"][category], row["levels"][level]["model_role_scores"][category])
                for row in ordered
            ]
            if any(a_raw < b_raw and a_score > b_score for a_raw, a_score in raw_score_pairs for b_raw, b_score in raw_score_pairs):
                issues.append(f"{level}:{category}:normalization_not_monotonic")
            scores = [row["levels"][level]["role_scores"][category] for row in eligible]
            if not scores or max(scores) < 95:
                issues.append(f"{level}:{category}:top_not_normalized")
            for row in eligible:
                final_score = row["levels"][level]["role_scores"][category]
                base_score = row["levels"][level]["model_role_scores"][category]
                signal = row["levels"][level]["observed_use_case_signals"][category]
                blog_bonus = row["levels"][level]["blog_prior_bonuses"][category]
                if final_score < base_score or (final_score != base_score and signal <= 0 and blog_bonus <= 0):
                    issues.append(f"{level}:{category}:{row['rating_id']}:invalid_observed_adjustment")
            distributions[f"{level}:{category}"] = {
                "candidate_count": len(scores), "min": min(scores), "median": statistics.median(scores), "max": max(scores),
            }

    for row in rows:
        level = row["levels"]["80"]
        for component in level["use_case_components"]["attack_front"]:
            if component["effect_kind"] in {"atk_buff", "ap_buff"} and "self" not in component["factors"]["recipients"]:
                issues.append(f"{row['rating_id']}:attack_front_non_self_buff")
        for category in ("attack_support", "defense_support"):
            for component in level["use_case_components"][category]:
                if component["effect_kind"] in {"atk_buff", "ap_buff", "def_buff", "damage_reduction", "damage_nullification", "hp_recovery"} and not (set(component["factors"]["recipients"]) & TEAM_RECIPIENTS):
                    issues.append(f"{row['rating_id']}:{category}:non_team_recipient")

    report = REPORT.read_text(encoding="utf-8")
    checks = {
        "six_use_cases": all(label in report for label in ("攻击车头", "守站肉盾", "攻击队友", "防守队友", "加分", "加经验")),
        "no_published_overall": ">总评<" not in report and "按总分" not in report,
        "compact_columns": all(label in report for label in ("用途分", "属性", "类型", "模型一句话推荐", "高价值配队观测", "Wiki评价", "Wiki评语", "博客评价", "博客评语")) and all(label not in report for label in (">概率<", ">覆盖<", ">启动条件<", ">核查评语<")),
        "attribute_type_filters": 'id="attribute"' in report and 'id="type"' in report,
        "extra_049_not_top10_lv50_attack": rank(rows, "extra:049", "50", "attack_front") > 10,
        "original_087_not_top10_lv50_attack": rank(rows, "original:087", "50", "attack_front") > 10,
    }
    if not all(checks.values()):
        issues.append("report_or_named_regression_failed")
    result = {
        "artifact": "step3_player_use_case_rating_audit", "rating_count": len(rows),
        "distributions": distributions, "checks": checks,
        "named_ranks": {
            "extra:049_lv50_attack_front": rank(rows, "extra:049", "50", "attack_front"),
            "original:087_lv50_attack_front": rank(rows, "original:087", "50", "attack_front"),
        },
        "issue_count": len(issues), "issues": sorted(set(issues)),
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"checks": len(checks), "issue_count": result["issue_count"], "named_ranks": result["named_ranks"]}, ensure_ascii=False))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
