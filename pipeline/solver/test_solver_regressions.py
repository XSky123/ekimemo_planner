from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline.solver.solve_team import component_evaluation, evaluations_for_best_positions, recipient_applies, solve  # noqa: E402


def profile(
    denko_id: str,
    effect_kind: str,
    recipient: list[str],
    value: float = 20,
    probability: float = 100,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "profile_id": f"{denko_id}#{effect_kind}",
        "denko": {"denko_id": denko_id, "name": denko_id, "pool": "fixture", "attribute": "cool", "type": "supporter"},
        "component": {
            "component_id": effect_kind,
            "effect_kind": effect_kind,
            "recipient": recipient,
            "availability": {"levels": ["50"], "vu_only": False},
            "level_values": {"50": {"value_numeric": value, "value_raw": str(value), "unit": "percent"}},
            "target_filters": filters or {},
            "source": {"condition_raw": None, "remarks_raw": None},
        },
        "activation": {"mode": "auto", "probability_by_level": {"50": {"parse_status": "exact", "percent": probability}}},
        "constraints": {"opportunity_costs": []},
        "scene_tags": [],
        "record_meta": {"source_url": "fixture://"},
    }


def request(scene: str) -> dict[str, Any]:
    return {"main_denko_id": "main", "scene": scene, "level": "50", "context": {"assume_main_access": True, "assume_main_accessed": True, "main_position": "front"}}


def main() -> int:
    members = [
        {"denko_id": "main", "attribute": "cool", "type": "attacker"},
        {"denko_id": "ally", "attribute": "heat", "type": "supporter"},
    ]
    checks: list[tuple[str, bool, str]] = []
    self_only = component_evaluation(profile("ally", "atk_buff", ["self"]), request("capture"), members)
    checks.append(("self_only_ally_is_not_main_support", self_only["status"] == "inactive", repr(self_only)))
    formation = component_evaluation(profile("ally", "atk_buff", ["team_all"], filters={"own_team_all_attribute": "cool"}), request("capture"), members)
    checks.append(("all_attribute_formation_is_checked_after_team_selection", formation["status"] == "inactive", repr(formation)))
    limited_profile = profile("ally", "atk_buff", ["team_all"], filters={"formation_only": True})
    limited_profile["component"]["source"]["condition_raw"] = "cool and heat only formation"
    limited = component_evaluation(limited_profile, request("capture"), members)
    checks.append(("allowed_attribute_formation_accepts_matching_team", limited["status"] == "active", repr(limited)))
    mixed_members = [*members, {"denko_id": "third", "attribute": "eco", "type": "supporter"}]
    blocked_formation = component_evaluation(limited_profile, request("capture"), mixed_members)
    checks.append(("allowed_attribute_formation_blocks_outside_attribute", blocked_formation["status"] == "inactive", repr(blocked_formation)))
    attribute_count = component_evaluation(profile("ally", "atk_buff", ["team_all"], filters={"own_team_attribute_min_count": {"attribute": "eco", "min_count": 2}}), request("capture"), members)
    checks.append(("own_attribute_min_count_uses_structured_shape", attribute_count["status"] == "inactive", repr(attribute_count)))
    probability = component_evaluation(profile("ally", "atk_buff", ["team_all"], value=20, probability=40), request("capture"), members)
    checks.append(("probability_multiplies_expected_not_maximum", probability["theoretical_max"] == 20 and probability["expected_value"] == 8, repr(probability)))
    ranged_profile = profile("ally", "atk_buff", ["team_all"], value=20)
    ranged_profile["activation"]["probability_by_level"]["50"] = {"parse_status": "range", "min_percent": 10, "max_percent": 50}
    ranged = component_evaluation(ranged_profile, request("capture"), members)
    checks.append(("probability_range_is_not_synthetic_mean", ranged["status"] == "active_unquantified" and ranged["expected_value"] is None, repr(ranged)))
    defense = component_evaluation(profile("ally", "def_buff", ["team_all"]), request("capture"), members)
    checks.append(("defense_does_not_leak_into_capture", defense["status"] == "inactive", repr(defense)))
    cool_context = solve({
        "main_denko_id": "original:026", "scene": "capture", "level": "50", "slots": 2,
        "allowed_denko_ids": ["extra:006"], "context": {"assume_main_access": True},
    })
    cool_active = [item["profile_id"] for team in cool_context["teams"] for item in team["active_components"]]
    checks.append(("accessor_station_condition_blocks_wrong_main", "extra:006#fixed_damage_1" not in cool_active and cool_context["candidate_summary"]["candidate_pool_size"] == 0, repr(cool_context)))
    eco_context = solve({
        "main_denko_id": "original:002", "scene": "capture", "level": "50", "slots": 2,
        "allowed_denko_ids": ["extra:006"], "context": {"assume_main_access": True, "station_attribute": "eco"},
    })
    eco_active = [item["profile_id"] for team in eco_context["teams"] for item in team["active_components"]]
    checks.append(("accessor_station_condition_allows_matching_main", "extra:006#fixed_damage_1" in eco_active, repr(eco_context["teams"])))
    opponent_count_request = request("capture")
    opponent_count_request["context"]["opponent_type"] = "supporter"
    opponent_count_request["context"]["opponent_type_counts"] = {"supporter": 2}
    opponent_count = component_evaluation(profile("ally", "def_debuff", ["opponent_denko"], filters={"opponent_type": "supporter", "opponent_type_count_min": 3}), opponent_count_request, members)
    checks.append(("opponent_type_count_is_explicit_context", opponent_count["status"] == "inactive", repr(opponent_count)))
    small_team = component_evaluation(profile("ally", "def_buff", ["team_all"], filters={"formation_size_min": 3}), request("defense"), members)
    checks.append(("formation_size_min_is_enforced", small_team["status"] == "inactive", repr(small_team)))
    mono_opponent_request = request("defense")
    mono_opponent_request["context"].update({"opponent_attribute_counts": {"heat": 3}, "opponent_team_size": 3})
    diversity = component_evaluation(profile("ally", "damage_cap", ["team_all"], filters={"opponent_team_attribute_diversity": "multiple_attributes"}), mono_opponent_request, members)
    checks.append(("opponent_attribute_diversity_is_enforced", diversity["status"] == "inactive", repr(diversity)))
    all_attr = component_evaluation(profile("ally", "def_buff", ["team_all"], filters={"opponent_team_all_attribute": "eco"}), mono_opponent_request, members)
    checks.append(("opponent_all_attribute_is_enforced", all_attr["status"] == "inactive", repr(all_attr)))
    temperature_request = request("capture")
    temperature_request["context"]["temperature_c"] = 30
    hot = component_evaluation(profile("ally", "atk_buff", ["team_all"], filters={"temperature_band": ">=30C"}), temperature_request, members)
    checks.append(("temperature_band_allows_matching_temperature", hot["status"] == "active", repr(hot)))
    gap_request = request("capture")
    gap_request["context"]["temperature_c"] = 12
    gap = component_evaluation(profile("ally", "atk_buff", ["team_all"], filters={"inactive_temperature_bands": ["11-14C"]}), gap_request, members)
    checks.append(("inactive_temperature_band_blocks_gap", gap["status"] == "inactive", repr(gap)))
    season_request = request("capture")
    season_request["context"]["month"] = 7
    season = component_evaluation(profile("ally", "atk_buff", ["team_all"], filters={"season_months": [6, 7, 8]}), season_request, members)
    checks.append(("season_months_accepts_current_month", season["status"] == "active", repr(season)))
    score_profile = profile("main", "score_random_modifier", ["self"], value=0)
    score_profile["component"]["level_values"]["50"].update({"value_expected": 198, "value_max": 750, "value_numeric": None})
    score_profile["activation"]["probability_by_level"]["50"] = {"parse_status": "branch_expected", "percent": None}
    score_expected = component_evaluation(score_profile, request("score_exp"), [members[0]])
    checks.append(("precomputed_branch_expected_score_is_not_double_weighted", score_expected["status"] == "active" and score_expected["expected_value"] == 198 and score_expected["theoretical_max"] == 750, repr(score_expected)))
    nullification = component_evaluation(profile("main", "skill_disable", ["opponent_denko"], value=55, probability=55), request("mechanism"), [members[0]])
    checks.append(("behavioral_percent_is_probability_not_effect_amount", nullification["status"] == "active" and nullification["theoretical_max"] == 1 and nullification["expected_value"] == 0.55, repr(nullification)))
    holder_damage = profile("ally", "fixed_damage", ["opponent_denko"])
    holder_damage["component"]["trigger_actor"] = "skill_holder"
    holder_applies, _ = recipient_applies(holder_damage, request("capture"), {"main", "ally"})
    checks.append(("holder_access_damage_is_not_main_support", not holder_applies, repr(holder_damage)))
    team_damage = profile("ally", "fixed_damage", ["opponent_denko"])
    team_damage["component"]["trigger_actor"] = "any_team_member"
    team_applies, _ = recipient_applies(team_damage, request("capture"), {"main", "ally"})
    checks.append(("team_access_damage_can_support_main", team_applies, repr(team_damage)))
    own_debuff_context = solve({
        "main_denko_id": "original:026", "scene": "capture", "level": "50", "slots": 2,
        "allowed_denko_ids": ["extra:008"], "context": {"assume_main_access": True},
    })
    checks.append(("own_team_debuff_is_not_capture_candidate", own_debuff_context["candidate_summary"]["candidate_pool_size"] == 0, repr(own_debuff_context)))
    relative_profile = profile("ally", "atk_buff", ["relative_car"], filters={"position_relative_to_self": "previous_car"})
    relative_evaluations, relative_positions, _ = evaluations_for_best_positions(("main", "ally"), members, [relative_profile], request("capture"))
    checks.append(("auto_positioning_places_holder_after_main_for_previous_car", relative_positions == {"main": 1, "ally": 2} and relative_evaluations[0]["status"] == "active", repr((relative_positions, relative_evaluations))))
    failures = [{"id": name, "detail": detail} for name, ok, detail in checks if not ok]
    print(json.dumps({"cases": len(checks), "failures": len(failures), "details": failures}, ensure_ascii=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
