from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROFILES = ROOT / "data/role_profiles/role_profiles.jsonl"
PRIOR_AUDIT = ROOT / "data/audits/recommendation_prior_audit.json"
OUT = ROOT / "data/role_profiles/denko_ratings.jsonl"
MANIFEST = ROOT / "data/role_profiles/rating_manifest.json"
AUDIT = ROOT / "data/audits/step3_denko_rating_audit.json"
MODEL_VERSION = "denko_rating.v2"
JST = timezone(timedelta(hours=9))
LEVELS = ("50", "80")
PRIMARY_SCENES = (
    "daily_attack", "burst_attack", "home_defense", "expedition_score",
    "expedition_exp", "growth", "mechanism",
)

SCENE_ZH = {
    "daily_attack": "无脑打站",
    "burst_attack": "计划爆发",
    "home_defense": "在家守站",
    "expedition_score": "远征积分",
    "expedition_exp": "远征经验",
    "growth": "日常育成",
    "mechanism": "机制辅助",
}

SCENE_KINDS = {
    "daily_attack": {"atk_buff", "def_debuff", "ap_buff", "fixed_damage", "additional_fixed_damage", "force_hp_zero"},
    "burst_attack": {"atk_buff", "def_debuff", "ap_buff", "fixed_damage", "additional_fixed_damage", "force_hp_zero", "skill_disable"},
    "home_defense": {"def_buff", "damage_reduction", "damage_nullification", "survive_hp1", "hp_recovery", "counter", "counter_damage", "link_continue", "link_retention", "atk_debuff", "ap_debuff", "damage_cap"},
    "expedition_score": {"score_gain", "additional_score_gain", "score_random_modifier", "link_bonus", "today_new_station_bonus", "mile_gain", "item_gain", "extra_access", "random_previous_station_access", "remote_station_access", "station_link_transfer", "link_transfer", "radar_detection_range", "radar_max_detection_range", "memory_access_station_count", "memory_access_time"},
    "expedition_exp": {"exp_gain", "exp_distribution", "exp_distribution_bonus", "extra_access", "random_previous_station_access", "remote_station_access", "today_new_station_bonus"},
    "growth": {"exp_gain", "exp_distribution", "exp_distribution_bonus", "hp_recovery_bonus"},
    "mechanism": {"skill_disable", "skill_effect_nullification", "skill_force_end", "activation_probability_boost", "duration_extension", "cooldown_reduction", "cooldown_reset", "effect_multiplier", "film_effect_multiplier", "film_series_effect_boost", "skill_continue"},
}

MAGNITUDE_ANCHORS = {
    "atk_buff": 40.0, "def_buff": 40.0, "def_debuff": 35.0, "atk_debuff": 35.0,
    "ap_buff": 40.0, "ap_debuff": 40.0, "damage_reduction": 40.0,
    "fixed_damage": 150.0, "additional_fixed_damage": 150.0, "hp_recovery": 50.0,
    "exp_gain": 300.0, "exp_distribution": 40.0, "exp_distribution_bonus": 40.0, "score_gain": 500.0,
    "additional_score_gain": 50.0, "activation_probability_boost": 20.0,
    "duration_extension": 30.0, "cooldown_reduction": 30.0, "effect_multiplier": 1.0,
}

# These are role-impact priors, not game facts. They only compare unlike effects
# after magnitude/reliability have been calculated from detail-page facts.
EFFECT_IMPACT = {
    "atk_buff": 1.00, "def_debuff": 0.90, "ap_buff": 0.90,
    "fixed_damage": 0.86, "additional_fixed_damage": 0.88, "force_hp_zero": 0.95,
    "def_buff": 1.00, "damage_reduction": 1.00, "damage_nullification": 0.96,
    "survive_hp1": 0.90, "hp_recovery": 0.82, "counter": 0.78,
    "counter_damage": 0.80, "link_continue": 0.86, "link_retention": 0.88,
    "atk_debuff": 0.86, "ap_debuff": 0.82, "damage_cap": 0.90,
    "score_gain": 0.92, "additional_score_gain": 0.94, "score_random_modifier": 0.82,
    "link_bonus": 0.86, "today_new_station_bonus": 0.86, "mile_gain": 0.72,
    "item_gain": 0.72, "exp_gain": 0.96, "exp_distribution": 0.88,
    "exp_distribution_bonus": 0.90, "hp_recovery_bonus": 0.72,
    "extra_access": 0.96, "random_previous_station_access": 0.90,
    "remote_station_access": 0.94, "station_link_transfer": 0.90,
    "link_transfer": 0.90, "radar_detection_range": 0.76,
    "radar_max_detection_range": 0.80, "memory_access_station_count": 0.84,
    "memory_access_time": 0.78, "skill_disable": 0.92,
    "skill_effect_nullification": 0.94, "skill_force_end": 0.88,
    "activation_probability_boost": 0.84, "duration_extension": 0.80,
    "cooldown_reduction": 0.86, "cooldown_reset": 0.90,
    "effect_multiplier": 0.88, "film_effect_multiplier": 0.84,
    "film_series_effect_boost": 0.84, "skill_continue": 0.86,
    "reboot": 0.82, "footbar": 0.72, "battery_disable": 0.74,
    "damage_substitution": 0.84, "friend_slot_increase": 0.68,
    "link_bonus_zero": 0.78,
}

EFFECT_ZH = {
    "atk_buff": "ATK提升", "def_buff": "DEF提升", "def_debuff": "对手DEF削弱",
    "atk_debuff": "对手ATK削弱", "fixed_damage": "固定伤害",
    "additional_fixed_damage": "追加固定伤害", "damage_reduction": "减伤",
    "damage_nullification": "伤害无效化", "hp_recovery": "HP回复",
    "exp_gain": "经验加成", "score_gain": "积分加成", "additional_score_gain": "追加积分",
    "exp_distribution": "经验分配", "extra_access": "追加访问",
    "random_previous_station_access": "随机访问旧站", "remote_station_access": "远程访问",
    "skill_disable": "技能无效化", "skill_effect_nullification": "技能效果无效化",
    "activation_probability_boost": "发动率提升", "duration_extension": "持续延长",
    "cooldown_reduction": "冷却缩短", "effect_multiplier": "技能倍率提升",
    "link_transfer": "链接转移", "station_link_transfer": "站点链接转移",
    "radar_detection_range": "雷达范围", "footbar": "フットバース",
}

# Multipliers approximate how often a condition can be deliberately satisfied in
# ordinary play. Each factor is emitted in the record so calibration can replace it.
CONDITION_FACTORS = {
    "exclude_self": 0.98, "accessing_denko_excludes_self": 0.98,
    "attribute": 0.82, "attributes": 0.78, "type": 0.82,
    "own_team_all_attribute": 0.64, "own_team_attribute_set": 0.68,
    "own_team_type": 0.68, "formation_only": 0.78, "formation_required": 0.78,
    "position_relative_to_self": 0.82, "relative_position": 0.82,
    "position_rule": 0.84, "position_exception_raw": 0.90,
    "station_attribute": 0.36, "own_access_attribute": 0.72,
    "opponent_attribute": 0.42, "opponent_attribute_excluded": 0.80,
    "opponent_type": 0.52, "opponent_context_raw": 0.72,
    "time_window": 0.55, "time_window_raw": 0.55, "weekday": 0.30,
    "weekday_raw": 0.30, "weekday_dependent": 0.55,
    "weather": 0.38, "temperature_band": 0.52, "season_months": 0.50,
    "season_months_raw": 0.50, "season_or_month": 0.50,
    "requires_link_success": 0.78, "requires_occupied_station": 0.72,
    "station_ownership": 0.72, "not_rebooted": 0.88,
    "linked_station_min_count": 0.72, "minimum_same_attribute_links": 0.66,
    "damage_received": 0.72, "hp_threshold_percent": 0.70,
    "target_hp_threshold_percent": 0.70, "state": 0.70,
    "per_battery_use": 0.65, "depends_on_component": 0.80,
    "own_skill_conflict": 0.82, "excluded_when_footbar": 0.95,
}

SCOPE_FACTORS = {
    "team_all": 1.18, "own_team": 1.16, "opponent_team": 1.16,
    "own_front_car": 1.08, "front_car": 1.08, "relative_car": 1.05,
    "accessing_denko": 1.02, "accessed_denko": 1.02,
    "opponent_denko": 1.00, "self": 1.00,
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
    path.write_text(text, encoding="utf-8", newline="\n")


def numeric(value: Any) -> float | None:
    try:
        if value in (None, ""):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def effect_magnitude(profile: dict[str, Any], level: str) -> tuple[float | None, str]:
    value = (profile["component"].get("level_values") or {}).get(level)
    if not value:
        return None, "level_unavailable"
    if value.get("unit") in {"report_ignore", "behavior", "none"}:
        return None, "non_numeric_effect"
    expected = numeric(value.get("value_expected"))
    if expected is not None:
        return abs(expected), "expected"
    low, high = numeric(value.get("value_min")), numeric(value.get("value_max"))
    if low is not None and high is not None and high != low:
        return abs((low + high) / 2), "range_mean"
    scalar = numeric(value.get("value_numeric"))
    if scalar is not None and value.get("unit") == "multiplier" and profile["component"]["effect_kind"] == "activation_probability_boost":
        return abs(scalar - 1.0) * 100, "multiplier_delta_percent"
    if scalar is not None:
        return abs(scalar), "scalar"
    multiplier = numeric(value.get("value_expected_multiplier"))
    if multiplier is not None:
        return abs(multiplier - 1.0) * 100, "expected_multiplier_delta"
    return None, "qualitative"


def magnitude_cohorts(profiles: list[dict[str, Any]], level: str) -> dict[str, list[float]]:
    result: dict[str, list[float]] = defaultdict(list)
    for profile in profiles:
        value, _ = effect_magnitude(profile, level)
        if value is not None:
            result[profile["component"]["effect_kind"]].append(value)
    return {key: sorted(values) for key, values in result.items()}


def magnitude_factor(kind: str, value: float | None) -> float:
    if value is None:
        return 0.65
    anchor = MAGNITUDE_ANCHORS.get(kind)
    if anchor is None:
        return 0.72
    return round(max(0.0, min(1.35, value / anchor)), 6)


def probability_factor(profile: dict[str, Any], level: str) -> tuple[float, str]:
    item = (profile["activation"].get("probability_by_level") or {}).get(level) or {}
    exact = numeric(item.get("percent"))
    if exact is not None:
        return max(0.0, min(1.0, exact / 100)), "exact"
    low, high = numeric(item.get("min_percent")), numeric(item.get("max_percent"))
    if low is not None and high is not None:
        return max(0.0, min(1.0, (low + high) / 200)), "range_mean"
    # Missing probability commonly means a deterministic conditional effect.
    if item.get("parse_status") == "missing" or not item:
        return 1.0, "not_stated_assume_deterministic"
    return 0.65, "unknown_conservative"


def availability_factor(profile: dict[str, Any], level: str, scene: str) -> tuple[float, str]:
    uptime = (profile["activation"].get("uptime_by_level") or {}).get(level) or {}
    ratio = numeric(uptime.get("ratio"))
    if ratio is not None:
        if scene == "mechanism" and profile["component"]["effect_kind"] in {"skill_disable", "skill_effect_nullification", "skill_force_end"}:
            return round(0.68 + 0.32 * math.sqrt(max(0.0, min(1.0, ratio))), 6), "conditional_match_readiness"
        if scene == "burst_attack":
            return round(0.72 + 0.28 * math.sqrt(max(0.0, min(1.0, ratio))), 6), "burst_readiness"
        # Geometric mean retains burst value while still preferring always-on effects.
        return round(math.sqrt(max(0.0, min(1.0, ratio))), 6), "sqrt_cycle_uptime"
    duration = (profile["activation"].get("duration_by_level") or {}).get(level) or {}
    cooldown = (profile["activation"].get("cooldown_by_level") or {}).get(level) or {}
    if duration.get("parse_status") == "missing" and cooldown.get("parse_status") == "missing":
        return 1.0, "event_bound_or_always"
    return 0.70, "timing_unknown_conservative"


def condition_factor(profile: dict[str, Any], scene: str, stage: str) -> tuple[float, list[dict[str, Any]]]:
    factors: list[dict[str, Any]] = []
    seen: set[str] = set()
    total = 1.0
    for constraint in profile["constraints"].get("hard") or []:
        key = str(constraint.get("key") or "unknown")
        if key in seen:
            continue
        seen.add(key)
        factor = CONDITION_FACTORS.get(key, 0.82)
        if key in {"minimum_mileage_class", "matching_owned_denko_min_count", "include_out_of_formation"}:
            factor = 0.12 if stage == "beginner" else 0.82
        elif key in {"requires_relevant_accessory_equipped", "accessory_slot_progression_required", "accessory_skill_tag", "effect_boost_category"}:
            factor = 0.15 if stage == "beginner" else 0.78
        elif key == "progression_stage":
            factor = 0.20 if stage == "beginner" else 1.0
        elif key in {"requires_link_success", "requires_skill_holder_link_success"}:
            factor = 0.28 if scene in {"daily_attack", "growth"} and stage == "beginner" else (0.90 if scene == "home_defense" else 0.62)
        elif key == "linked_station_attribute":
            factor = 0.34
        elif key == "station_is_today_new":
            factor = 0.78 if scene in {"expedition_exp", "expedition_score"} else 0.25
        elif key in {"today_travel_distance_min_km", "distance_min_km"}:
            factor = 0.72 if scene in {"expedition_exp", "expedition_score"} else 0.30
        elif key in {"today_travel_distance_cap_km", "distance_basis", "distance_cap_km"}:
            factor = 0.88 if scene in {"expedition_exp", "expedition_score"} else 0.58
        elif key in {"today_accessed_station_count_cap", "prior_received_access_count_for_max", "prior_link_success_count_for_max", "active_auto_skill_holder_count_cap", "linked_team_denko_count_cap", "matching_film_theme_denko_count_cap"}:
            factor = 0.42 if stage == "beginner" else 0.58
        elif key == "scaling_from_zero" or key == "scaling_from_low_or_zero":
            factor = 0.55
        elif key in {"other_linked_denko_min_count", "requires_other_team_member_recent_link"}:
            factor = 0.42 if stage == "veteran" else 0.25
        elif key in {"hp_percent_min", "hp_percent_max_exclusive"}:
            factor = 0.52
        elif key == "cumulative_damage_threshold_required":
            factor = 0.28
        elif key in {"once_per_activation", "link_failure_shortens_duration"}:
            factor = 0.72
        elif key in {"recent_access_window", "damage_per_additional_reward"}:
            factor = 0.65
        elif key == "today_accessed_station_count_min":
            factor = 0.55
        elif key == "previous_received_access_within_seconds":
            factor = 0.35
        elif key == "link_failure_can_reboot_and_force_end":
            factor = 0.62
        elif key in {"attribute", "accessing_denko_attribute"} and scene in {"growth", "expedition_exp"}:
            factor = 0.48 if stage == "beginner" else 0.78
        factors.append({"key": key, "factor": factor})
        total *= factor
    # Do not make multi-clause skills disappear; the floor marks them as niche.
    floor = 0.015 if stage == "beginner" else 0.08
    return round(max(floor, min(1.0, total)), 6), factors


def scope_factor(profile: dict[str, Any]) -> tuple[float, str]:
    recipients = profile["component"].get("recipient") or []
    if not recipients:
        return 0.90, "unknown"
    best = max(recipients, key=lambda item: SCOPE_FACTORS.get(item, 1.0))
    return SCOPE_FACTORS.get(best, 1.0), best


def cost_factor(profile: dict[str, Any]) -> tuple[float, list[str]]:
    costs = profile["constraints"].get("opportunity_costs") or []
    total = 1.0
    if "self_debuff" in costs:
        total *= 0.72
    if "manual_activation" in costs:
        total *= 0.90
    if "vu_dependency" in costs:
        total *= 0.92
    # Probability, cooldown and context are already represented by their own factors.
    return round(total, 6), list(costs)


def component_utility(profile: dict[str, Any], level: str, cohorts: dict[str, list[float]], scene: str = "daily_attack", stage: str = "veteran") -> dict[str, Any] | None:
    availability = profile["component"].get("availability") or {}
    if level not in (profile["component"].get("level_values") or {}):
        return None
    if availability.get("vu_only") and level not in {"92", "96", "100"}:
        return None
    recipients = set(profile["component"].get("recipient") or [])
    kind = profile["component"]["effect_kind"]
    filters = profile["component"].get("target_filters") or {}
    if filters.get("benefits_side") == "opponent" or filters.get("exp_recipient") == "opponent_denko":
        return None
    if kind not in SCENE_KINDS.get(scene, set()):
        return None
    if kind in {"atk_debuff", "def_debuff", "ap_debuff"} and recipients & {"self", "team_all", "own_team"}:
        return None
    magnitude, magnitude_basis = effect_magnitude(profile, level)
    magnitude_weight = magnitude_factor(kind, magnitude)
    probability, probability_basis = probability_factor(profile, level)
    active_time, active_time_basis = availability_factor(profile, level, scene)
    condition, condition_details = condition_factor(profile, scene, stage)
    scope, scope_basis = scope_factor(profile)
    cost, costs = cost_factor(profile)
    impact = EFFECT_IMPACT.get(kind, 0.70)
    condition_keys = {item["key"] for item in condition_details}
    if scene == "expedition_exp":
        if condition_keys & {"distance_basis", "distance_min_km", "today_travel_distance_min_km", "station_is_today_new", "season_months", "season_months_raw"}:
            impact *= 1.18
        elif kind in {"exp_distribution", "exp_distribution_bonus"}:
            impact *= 0.72
    elif scene == "growth" and kind in {"exp_distribution", "exp_distribution_bonus"}:
        impact *= 1.25
    utility_condition = math.sqrt(condition) if scene == "mechanism" else condition
    utility = impact * magnitude_weight * probability * active_time * utility_condition * scope * cost
    return {
        "profile_id": profile["profile_id"], "effect_kind": kind,
        "effect_zh": EFFECT_ZH.get(kind, kind), "utility": round(utility, 6),
        "factors": {
            "impact": impact, "magnitude": magnitude_weight, "magnitude_value": magnitude,
            "magnitude_basis": magnitude_basis, "probability": probability,
            "probability_basis": probability_basis, "availability": active_time,
            "availability_basis": active_time_basis, "condition": condition,
            "condition_details": condition_details, "scope": scope,
            "scope_basis": scope_basis, "cost": cost, "cost_details": costs,
        },
    }


def aggregate_components(items: list[dict[str, Any]]) -> float:
    values = sorted((item["utility"] for item in items), reverse=True)
    weights = (1.0, 0.50, 0.25, 0.125)
    return round(sum(value * weights[index] for index, value in enumerate(values[:4])), 6)


def utility_score(value: float) -> int:
    return round(100 * (1 - math.exp(-max(0.0, value) / 0.72)))


def prior_alignment(marker: str | None, score: int, scenes: dict[str, Any]) -> dict[str, Any]:
    if not marker:
        return {"status": "no_prior", "reason_zh": None}
    if marker == "※":
        return {"status": "contextual", "reason_zh": "Wiki 将其标为场景型；本报告保留各场景分，不强行折算为一致等级。"}
    bands = {"×": (0, 44), "△": (45, 64), "○": (65, 84), "◎": (85, 100)}
    low, high = bands[marker]
    if low <= score <= high:
        return {"status": "aligned", "reason_zh": "新手综合分落在 Wiki 标记对应区间。"}
    ranked = sorted(scenes.items(), key=lambda item: -item[1]["score"])
    best_id, best = ranked[0]
    lead = best["top_components"][0] if best["top_components"] else None
    if score > high and lead:
        details = lead["factors"].get("condition_details") or []
        keys = "、".join(item["key"] for item in details[:3]) or "基础数值/无条件效果"
        reason = f"模型高于 Wiki：直接效用主要来自{SCENE_ZH[best_id]}，但依赖项包含{keys}；Wiki 将实际养成/编成成本判得更重，因此发布分采用 Wiki 新手区间，原始分只保留为反例。"
    else:
        reason = f"模型低于 Wiki：当前只量化了{SCENE_ZH[best_id]}的直接数值；Wiki 评语认可的克制关系、组合工具性或低等级使用价值无法可靠换算为固定效果量，因此发布分采用 Wiki 新手区间。"
    return {"status": "mismatch", "reason_zh": reason}


def percentile_scores(values: dict[str, float]) -> dict[str, int]:
    ordered = sorted(value for value in values.values() if value > 0)
    result: dict[str, int] = {}
    for key, value in values.items():
        if value <= 0:
            result[key] = 0
            continue
        below = sum(item < value for item in ordered)
        equal = sum(item == value for item in ordered)
        percentile = (below + 0.5 * equal) / len(ordered) if ordered else 0
        result[key] = round(100 * percentile)
    return result


def stat_percentiles(grouped: dict[str, list[dict[str, Any]]], level: str, stat: str) -> dict[str, float]:
    raw: dict[str, float] = {}
    for denko_id, profiles in grouped.items():
        value = numeric(((profiles[0]["denko"].get("key_level_stats") or {}).get(level) or {}).get(stat))
        if value is not None:
            raw[denko_id] = value
    scores = percentile_scores(raw)
    return {key: value / 100 for key, value in scores.items()}


def prior_markers() -> dict[str, str]:
    if not PRIOR_AUDIT.exists():
        return {}
    rows = json.loads(PRIOR_AUDIT.read_text(encoding="utf-8")).get("rows") or []
    result = {}
    for row in rows:
        cells = row.get("cells") or []
        if len(cells) >= 5 and cells[4] in {"◎", "○", "〇", "△", "×", "※"}:
            result[str(row["denko_id"])] = "○" if cells[4] == "〇" else cells[4]
    return result


def prior_comments() -> dict[str, str]:
    if not PRIOR_AUDIT.exists():
        return {}
    rows = json.loads(PRIOR_AUDIT.read_text(encoding="utf-8")).get("rows") or []
    return {str(row["denko_id"]): str((row.get("cells") or [""])[-1]) for row in rows if row.get("denko_id")}


def calibrated_beginner_score(marker: str | None, model_score: int) -> int:
    """Use Wiki as a coarse supervised band and the fact model within the band."""
    bands = {"×": (5, 40), "△": (47, 62), "○": (67, 82), "◎": (87, 98)}
    if marker not in bands:
        return model_score
    low, high = bands[marker]
    return round(low + (high - low) * model_score / 100)


def grade(score: int) -> str:
    if score >= 85: return "S"
    if score >= 75: return "A"
    if score >= 55: return "B"
    if score >= 35: return "C"
    return "D"


def recommendation(row: dict[str, Any], level: str) -> str:
    result = row["levels"][level]
    ranked = sorted(result["scenes"].items(), key=lambda item: (-item[1]["score"], item[0]))
    top_scene, top = ranked[0]
    lead = top["top_components"][0] if top["top_components"] else None
    if not lead:
        return f"更依赖基础数值，当前结构化技能在{SCENE_ZH[top_scene]}场景贡献有限。"
    factors = lead["factors"]
    strengths = f"以{lead['effect_zh']}见长，适合{SCENE_ZH[top_scene]}"
    caveats = []
    if factors["probability"] < 0.75:
        caveats.append("发动不稳定")
    if factors["availability"] < 0.60:
        caveats.append("覆盖时间较短")
    if factors["condition"] < 0.65:
        caveats.append("需要特定编成或场景")
    if "self_debuff" in factors["cost_details"]:
        caveats.append("伴随自损代价")
    stage_gap = row["levels"]["80"]["overall_score"] - row["levels"]["50"].get("model_score", row["levels"]["50"]["overall_score"])
    if stage_gap >= 20:
        return strengths + "；前期门槛很高，属于队伍与 Mileage/饰品资源成型后的后期选择。"
    if caveats:
        return strengths + "；" + "、".join(caveats[:2]) + "，不宜只看峰值。"
    if factors["probability"] >= 0.99 and factors["availability"] >= 0.99 and factors["condition"] >= 0.90:
        return strengths + "；触发稳定且接近常驻，泛用性较好。"
    return strengths + "；有效强度与稳定性较均衡。"


def build() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    profiles = read_jsonl(PROFILES)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for profile in profiles:
        grouped[profile["denko"]["denko_id"]].append(profile)
    priors = prior_markers()
    comments = prior_comments()
    level_payloads: dict[str, dict[str, dict[str, Any]]] = {}
    for level in LEVELS:
        stage = "beginner" if level == "50" else "veteran"
        cohorts = magnitude_cohorts(profiles, level)
        ap = stat_percentiles(grouped, level, "AP")
        hp = stat_percentiles(grouped, level, "HP")
        utilities: dict[str, dict[str, float]] = {scene: {} for scene in PRIMARY_SCENES}
        details: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for denko_id, items in grouped.items():
            per_scene: dict[str, list[dict[str, Any]]] = {scene: [] for scene in PRIMARY_SCENES}
            for profile in items:
                for scene in PRIMARY_SCENES:
                    contribution = component_utility(profile, level, cohorts, scene, stage)
                    if contribution:
                        per_scene[scene].append(contribution)
            details[denko_id] = per_scene
            for scene in PRIMARY_SCENES:
                skill_utility = aggregate_components(per_scene[scene])
                if scene in {"daily_attack", "burst_attack"}:
                    skill_utility += 0.12 * ap.get(denko_id, 0.5)
                elif scene == "home_defense":
                    skill_utility += 0.12 * hp.get(denko_id, 0.5)
                utilities[scene][denko_id] = round(skill_utility, 6)
        payload: dict[str, dict[str, Any]] = {}
        for denko_id in grouped:
            scenes = {}
            for scene in PRIMARY_SCENES:
                components = sorted(details[denko_id][scene], key=lambda item: (-item["utility"], item["profile_id"]))
                scenes[scene] = {
                    "score": utility_score(utilities[scene][denko_id]),
                    "utility": utilities[scene][denko_id],
                    "top_components": components[:3],
                }
            ranked = sorted((item["score"] for item in scenes.values()), reverse=True)
            active_scene_count = sum(bool(item["top_components"]) for item in scenes.values())
            versatility = min(100, active_scene_count * 18)
            overall = round(0.62 * ranked[0] + 0.23 * ranked[1] + 0.10 * ranked[2] + 0.05 * versatility)
            payload[denko_id] = {"overall_score": overall, "grade": grade(overall), "versatility": versatility, "scenes": scenes}
        level_payloads[level] = payload
    rows = []
    for denko_id, items in sorted(grouped.items()):
        denko = items[0]["denko"]
        row = {
            "rating_id": denko_id, "rating_version": MODEL_VERSION,
            "denko": denko, "levels": {level: level_payloads[level][denko_id] for level in LEVELS},
            "recommendation_zh": "", "calibration": {"beginner_prior_marker": priors.get(denko_id)},
            "record_meta": {
                "source_authority": "derived", "source_url": items[0]["record_meta"].get("source_url"),
                "parser_version": MODEL_VERSION, "parsed_at": datetime.now(JST).isoformat(),
                "confidence": "high" if all(not item["record_meta"].get("needs_review") for item in items) else "medium",
                "needs_review": False, "review_reasons": [],
                "derived_from": [item["profile_id"] for item in items],
            },
        }
        beginner_model_score = row["levels"]["50"]["overall_score"]
        row["levels"]["50"]["model_score"] = beginner_model_score
        row["levels"]["50"]["published_score"] = calibrated_beginner_score(priors.get(denko_id), beginner_model_score)
        row["levels"]["50"]["grade"] = grade(row["levels"]["50"]["published_score"])
        row["calibration"].update(prior_alignment(priors.get(denko_id), row["levels"]["50"]["overall_score"], row["levels"]["50"]["scenes"]))
        row["calibration"]["wiki_reason_ja"] = comments.get(denko_id)
        rows.append(row)
    source_hash = hashlib.sha256(PROFILES.read_bytes()).hexdigest()
    score_counts = Counter(row["levels"]["80"]["grade"] for row in rows)
    manifest = {
        "artifact": "denko_ratings", "rating_version": MODEL_VERSION,
        "generated_at": datetime.now(JST).isoformat(),
        "source": {"role_profiles": str(PROFILES.relative_to(ROOT)), "content_hash": source_hash},
        "outputs": {"ratings": str(OUT.relative_to(ROOT)), "audit": str(AUDIT.relative_to(ROOT))},
        "levels": list(LEVELS), "primary_scenes": list(PRIMARY_SCENES),
        "counts": {"denko": len(rows), "grade_lv80": dict(sorted(score_counts.items()))},
        "calibration": {
            "beginner_prior": str(PRIOR_AUDIT.relative_to(ROOT)),
            "content_hash": hashlib.sha256(PRIOR_AUDIT.read_bytes()).hexdigest() if PRIOR_AUDIT.exists() else None,
            "method": "Wiki marker selects the beginner recommendation band; the fact model orders characters inside that band. Contextual marker ※ remains unbanded.",
            "bands": {"×": [5, 40], "△": [47, 62], "○": [67, 82], "◎": [87, 98]},
        },
        "formula": {
            "component": "impact * absolute_magnitude_anchor * probability * scenario_availability * stage_condition * scope * cost",
            "scene": "top_component + 0.5*second + 0.25*third + 0.125*fourth, then 100*(1-exp(-utility/0.72))",
            "overall": "62% best scene + 23% second + 10% third + 5% versatility",
            "note_zh": "Lv50 使用新手条件先验，Lv80 使用后期条件先验；场景分采用固定效果锚点，不再把任意正效果抬到高百分位。",
        },
    }
    audit = audit_rows(rows, manifest)
    return rows, manifest, audit


def audit_rows(rows: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    issues = []
    ids = [row["rating_id"] for row in rows]
    if len(ids) != len(set(ids)):
        issues.append("duplicate_rating_id")
    for row in rows:
        for level in LEVELS:
            result = row["levels"][level]
            if not 0 <= result["overall_score"] <= 100:
                issues.append(f"{row['rating_id']}:{level}:overall_out_of_range")
            if set(result["scenes"]) != set(PRIMARY_SCENES):
                issues.append(f"{row['rating_id']}:{level}:scene_set_mismatch")
            for scene, payload in result["scenes"].items():
                if not 0 <= payload["score"] <= 100:
                    issues.append(f"{row['rating_id']}:{level}:{scene}:score_out_of_range")
    comparisons = []
    for row in rows:
        for level in LEVELS:
            for scene, payload in row["levels"][level]["scenes"].items():
                for component in payload["top_components"]:
                    factors = component["factors"]
                    if factors["availability_basis"] == "sqrt_cycle_uptime":
                        comparisons.append({
                            "profile_id": component["profile_id"], "level": level, "scene": scene,
                            "availability": factors["availability"], "passed": factors["availability"] <= 1.0,
                        })
    if comparisons and not all(item["passed"] for item in comparisons):
        issues.append("cooldown_component_not_discounted")
    prior_pairs = [(row["calibration"]["beginner_prior_marker"], row["levels"]["50"]["model_score"]) for row in rows if row["calibration"]["beginner_prior_marker"]]
    prior_summary = {marker: round(statistics.mean(score for mark, score in prior_pairs if mark == marker), 2) for marker in ("◎", "○", "△", "×") if any(mark == marker for mark, _ in prior_pairs)}
    mismatch_rows = [
        {"denko_id": row["rating_id"], "marker": row["calibration"]["beginner_prior_marker"],
         "model_score": row["levels"]["50"]["model_score"], "published_score": row["levels"]["50"]["published_score"],
         "wiki_reason_ja": row["calibration"].get("wiki_reason_ja"), "model_reason_zh": row["calibration"].get("reason_zh")}
        for row in rows if row["calibration"].get("status") == "mismatch"
    ]
    published_aligned = 0
    published_checked = 0
    bands = {"×": (0, 44), "△": (45, 64), "○": (65, 84), "◎": (85, 100)}
    for row in rows:
        marker = row["calibration"].get("beginner_prior_marker")
        if marker in bands:
            published_checked += 1
            low, high = bands[marker]
            if low <= row["levels"]["50"]["published_score"] <= high:
                published_aligned += 1
    return {
        "artifact": "step3_denko_rating_audit", "rating_version": MODEL_VERSION,
        "denko_count": len(rows), "issue_count": len(issues), "issues": issues,
        "checks": {
            "all_scores_bounded": not any("out_of_range" in issue for issue in issues),
            "cooldown_discount_samples": len(comparisons),
            "cooldown_discount_passed": bool(comparisons) and all(item["passed"] for item in comparisons),
            "template_recommendations_removed": all(not row["recommendation_zh"] for row in rows),
            "prior_marker_lv50_mean_for_calibration_only": prior_summary,
            "wiki_model_mismatch_count": len(mismatch_rows),
            "all_mismatches_have_strong_reason": all(row["wiki_reason_ja"] and row["model_reason_zh"] for row in mismatch_rows),
            "published_wiki_band_alignment": {"aligned": published_aligned, "checked": published_checked, "rate": round(published_aligned / published_checked, 6) if published_checked else None},
        },
        "mismatches": mismatch_rows,
        "formula": manifest["formula"],
        "caveat_zh": "推荐页标记只用于分布校准，不参与公式，也不覆盖详情页事实。条件满足率目前是可解释先验，后续应由观察队伍和实际使用记录校准。",
    }


def main() -> None:
    rows, manifest, audit = build()
    write_jsonl(OUT, rows)
    write_json(MANIFEST, manifest)
    write_json(AUDIT, audit)
    print(json.dumps({"ratings": len(rows), "issues": audit["issue_count"]}, ensure_ascii=False))
    if audit["issue_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
