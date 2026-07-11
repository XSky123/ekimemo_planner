from __future__ import annotations

import copy
import json
from pathlib import Path

from score_denko_ratings import component_utility, read_jsonl


ROOT = Path(__file__).resolve().parents[2]
PROFILES = ROOT / "data/role_profiles/role_profiles.jsonl"
RATINGS = ROOT / "data/role_profiles/denko_ratings.jsonl"
OUT = ROOT / "data/audits/step3_denko_rating_regressions.json"


def base_profile() -> dict:
    for profile in read_jsonl(PROFILES):
        if profile["component"]["effect_kind"] == "atk_buff" and "50" in profile["component"]["level_values"]:
            row = copy.deepcopy(profile)
            row["component"]["recipient"] = ["team_all"]
            row["component"]["availability"] = {"vu_only": False}
            row["component"]["level_values"]["50"] = {
                "value_raw": "ATK +10%", "value_numeric": 10, "value_min": None,
                "value_max": None, "value_expected": None, "value_expected_multiplier": None,
                "options": None, "unit": "percent", "source_text": "synthetic regression",
            }
            row["activation"]["probability_by_level"]["50"] = {"parse_status": "exact", "percent": 100.0}
            row["constraints"] = {"hard": [], "opportunity_costs": [], "self_debuff": []}
            return row
    raise AssertionError("atk_buff fixture not found")


def main() -> int:
    cohort = {"atk_buff": [5.0, 10.0, 20.0]}
    always = base_profile()
    always["profile_id"] = "synthetic:always#atk_buff"
    always["activation"]["duration_by_level"]["50"] = {"parse_status": "missing", "seconds": None}
    always["activation"]["cooldown_by_level"]["50"] = {"parse_status": "missing", "seconds": None}
    always["activation"]["uptime_by_level"]["50"] = {"status": "unknown", "ratio": None}
    cooldown = copy.deepcopy(always)
    cooldown["profile_id"] = "synthetic:cooldown#atk_buff"
    cooldown["activation"]["duration_by_level"]["50"] = {"parse_status": "exact", "seconds": 900}
    cooldown["activation"]["cooldown_by_level"]["50"] = {"parse_status": "exact", "seconds": 5400}
    cooldown["activation"]["uptime_by_level"]["50"] = {"status": "estimated", "ratio": 900 / 6300}
    probabilistic = copy.deepcopy(always)
    probabilistic["profile_id"] = "synthetic:probability#atk_buff"
    probabilistic["activation"]["probability_by_level"]["50"] = {"parse_status": "exact", "percent": 40.0}
    constrained = copy.deepcopy(always)
    constrained["profile_id"] = "synthetic:condition#atk_buff"
    constrained["constraints"]["hard"] = [{"key": "own_team_all_attribute", "value": "heat", "source": "synthetic"}]
    utilities = {name: component_utility(profile, "50", cohort) for name, profile in {
        "always": always, "cooldown": cooldown, "probabilistic": probabilistic, "constrained": constrained,
    }.items()}
    checks = [
        {"id": "same_10_percent_always_beats_cooldown", "passed": utilities["always"]["utility"] > utilities["cooldown"]["utility"]},
        {"id": "same_10_percent_certain_beats_probability", "passed": utilities["always"]["utility"] > utilities["probabilistic"]["utility"]},
        {"id": "same_10_percent_unconditional_beats_formation_constraint", "passed": utilities["always"]["utility"] > utilities["constrained"]["utility"]},
        {"id": "cooldown_keeps_burst_value", "passed": utilities["cooldown"]["utility"] > 0},
    ]
    ratings = {row["rating_id"]: row for row in read_jsonl(RATINGS)}
    for denko_id in ("extra:110", "extra:111", "extra:112"):
        row = ratings[denko_id]
        checks.append({
            "id": f"{denko_id}_beginner_low_veteran_recovery",
            "passed": row["levels"]["50"]["published_score"] <= 40 and row["levels"]["80"]["overall_score"] >= 45,
        })
    checks.extend([
        {"id": "original_081_stays_wiki_triangle", "passed": 45 <= ratings["original:081"]["levels"]["50"]["published_score"] <= 64},
        {"id": "original_083_link_branch_not_high_generalist", "passed": ratings["original:083"]["levels"]["50"]["overall_score"] < 40},
        {"id": "extra_119_accessory_dependency_beginner_low", "passed": ratings["extra:119"]["levels"]["50"]["published_score"] <= 40},
        {"id": "all_wiki_band_scores_aligned", "passed": all(
            row["calibration"].get("status") in {"no_prior", "contextual"}
            or ({"×": (0, 44), "△": (45, 64), "○": (65, 84), "◎": (85, 100)}[row["calibration"]["beginner_prior_marker"]][0]
                <= row["levels"]["50"]["published_score"]
                <= {"×": (0, 44), "△": (45, 64), "○": (65, 84), "◎": (85, 100)}[row["calibration"]["beginner_prior_marker"]][1])
            for row in ratings.values()
        )},
    ])
    result = {
        "artifact": "step3_denko_rating_regressions", "checks": checks,
        "utilities": {key: value["utility"] for key, value in utilities.items()},
        "issue_count": sum(not check["passed"] for check in checks),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result["issue_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
