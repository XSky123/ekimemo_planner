from __future__ import annotations

import argparse
import copy
import hashlib
import itertools
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[2]
PROFILES_PATH = ROOT / "data" / "role_profiles" / "role_profiles.jsonl"
REQUEST_SCHEMA = ROOT / "schemas" / "solver_request.schema.json"
RESULT_SCHEMA = ROOT / "schemas" / "solver_result.schema.json"
SOLVER_VERSION = "step4_solver.v1"
JST = timezone(timedelta(hours=9))

SCENE_EFFECTS = {
    "capture": {"atk_buff", "ap_buff", "fixed_damage", "additional_fixed_damage", "def_debuff", "ap_debuff", "skill_disable", "skill_effect_nullification", "force_hp_zero"},
    "defense": {"def_buff", "atk_debuff", "damage_reduction", "hp_recovery", "hp_recovery_bonus", "survive_hp1", "damage_nullification", "damage_cap", "damage_substitution", "link_continue", "link_retention", "counter", "counter_damage", "reboot", "link_transfer", "station_link_transfer"},
    "commute": set(),
    "expedition": {"extra_access", "random_previous_station_access", "remote_station_access", "station_link_transfer", "link_transfer", "radar_detection_range", "radar_max_detection_range", "link_bonus", "memory_access_station_count", "memory_access_time"},
    "visit_count_event": {"extra_access", "random_previous_station_access", "remote_station_access", "station_link_transfer", "link_transfer"},
    "score_exp": {"exp_gain", "exp_distribution", "exp_distribution_bonus", "score_gain", "additional_score_gain", "score_random_modifier", "match_bonus", "mile_gain", "today_new_station_bonus", "item_gain"},
    "growth": {"exp_gain", "exp_distribution", "exp_distribution_bonus", "match_bonus"},
    "mechanism": {"skill_disable", "skill_effect_nullification", "skill_force_end", "battery_disable", "footbar", "force_hp_zero", "activation_probability_boost", "cooldown_reduction", "cooldown_reset", "cooldown_entry", "duration_extension", "effect_multiplier", "film_effect_multiplier", "film_series_effect_boost", "skill_continue"},
}

METRIC_BY_EFFECT = {
    "atk_buff": "atk_percent", "ap_buff": "ap_percent", "fixed_damage": "fixed_damage", "additional_fixed_damage": "fixed_damage",
    "def_debuff": "enemy_def_debuff_percent", "ap_debuff": "enemy_ap_debuff_percent", "skill_disable": "skill_interference",
    "skill_effect_nullification": "skill_interference", "force_hp_zero": "skill_interference",
    "def_buff": "def_percent", "atk_debuff": "enemy_atk_debuff_percent", "damage_reduction": "damage_reduction",
    "hp_recovery": "hp_recovery", "hp_recovery_bonus": "hp_recovery_bonus", "survive_hp1": "survival_effect",
    "damage_nullification": "survival_effect", "damage_cap": "damage_cap", "damage_substitution": "damage_substitution",
    "link_continue": "link_retention", "link_retention": "link_retention", "counter": "counter", "counter_damage": "counter_damage", "reboot": "reboot",
    "exp_gain": "exp_gain", "exp_distribution": "exp_distribution_percent", "exp_distribution_bonus": "exp_distribution_bonus",
    "score_gain": "score_gain", "additional_score_gain": "score_gain", "score_random_modifier": "score_modifier",
    "match_bonus": "match_bonus_percent", "mile_gain": "mile_gain", "today_new_station_bonus": "new_station_bonus", "item_gain": "item_gain",
    "extra_access": "extra_access", "random_previous_station_access": "access_tool", "remote_station_access": "access_tool",
    "station_link_transfer": "link_transfer", "link_transfer": "link_transfer", "radar_detection_range": "radar_range",
    "radar_max_detection_range": "radar_max_range", "memory_access_station_count": "memory_access_station_count", "memory_access_time": "memory_access_time",
    "activation_probability_boost": "probability_operation", "cooldown_reduction": "cooldown_operation", "cooldown_reset": "cooldown_operation",
    "duration_extension": "duration_operation", "effect_multiplier": "effect_multiplier", "film_effect_multiplier": "film_effect_multiplier",
    "film_series_effect_boost": "film_effect_multiplier", "skill_continue": "skill_continue",
}

BEHAVIORAL_EFFECTS = {
    "skill_disable", "skill_effect_nullification", "force_hp_zero", "survive_hp1", "damage_nullification",
    "damage_substitution", "link_continue", "link_retention", "reboot", "random_previous_station_access",
    "remote_station_access", "station_link_transfer", "link_transfer", "skill_continue",
}

RECIPIENT_LABEL_ZH = {
    "self": "自己", "team_all": "编成内全员", "own_team": "己方编成", "opponent_denko": "对手でんこ",
    "opponent_team": "对手编成", "accessing_denko": "访问中的でんこ", "accessed_denko": "被访问的でんこ",
    "front_car": "先头车", "own_front_car": "己方先头", "relative_car": "相对车位", "own_skill_effects": "自身技能效果",
    "master": "Master", "master_account": "Master账号",
}

HANDLED_FILTER_KEYS = {
    "attribute", "attributes", "type", "own_access_attribute", "station_attribute", "opponent_attribute", "opponent_type",
    "opponent_pool_in", "opponent_attribute_excluded", "opponent_pool_excludes", "weather", "weekday", "temperature_min_c",
    "temperature_max_c", "temperature_band", "inactive_temperature_bands", "season_months", "season_months_raw", "time_window", "time_window_raw",
    "weekday_raw", "formation_only", "disabled_skill_kind", "disabled_skill_target", "own_skill_conflict", "excluded_when_footbar",
    "position_relative_to_self", "relative_position",
    "own_team_all_attribute", "own_team_attribute_min_count", "formation_size_min",
    "opponent_team_attribute_min_count", "opponent_team_attribute_diversity",
    "opponent_team_all_attribute", "opponent_type_count_min",
    "minimum_link_minutes", "requires_occupied_station", "exclude_self",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(value: Any, schema_path: Path) -> None:
    errors = sorted(Draft202012Validator(read_json(schema_path)).iter_errors(value), key=lambda item: list(item.path))
    if errors:
        formatted = "; ".join(f"{'/'.join(map(str, error.path)) or '<root>'}: {error.message}" for error in errors[:8])
        raise ValueError(f"schema validation failed: {formatted}")


def level_value(profile: dict[str, Any], level: str) -> dict[str, Any] | None:
    values = profile["component"].get("level_values") or {}
    if level in values:
        return values[level]
    return None


def probability_factor(profile: dict[str, Any], level: str) -> tuple[float | None, str]:
    row = (profile["activation"].get("probability_by_level") or {}).get(level) or {}
    if row.get("parse_status") == "exact" and row.get("percent") is not None:
        return max(0.0, min(1.0, float(row["percent"]) / 100.0)), "exact"
    if row.get("parse_status") == "range" and row.get("min_percent") is not None and row.get("max_percent") is not None:
        # A contextual range is a documented uncertainty, not evidence for a
        # synthetic average. Keep the component visible but out of numeric
        # expected-value comparison until the caller supplies a scenario model.
        return None, "range_unquantified"
    return 1.0, "unrecorded_assumed_full"


def effect_magnitude(profile: dict[str, Any], level: str) -> tuple[float | None, str | None, str | None]:
    value = level_value(profile, level)
    if value is None:
        return None, None, "该等级效果未记载"
    raw = value.get("value_numeric")
    kind = profile["component"].get("effect_kind")
    metric = METRIC_BY_EFFECT.get(kind)
    if metric is None:
        return None, None, "该效果尚未定义可比较量纲"
    # For behavioral effects, a parsed percent is usually the activation rate
    # duplicated from a merged wiki table, not a second independent magnitude.
    # Use one effect instance and let probability_factor produce its expectation.
    if kind in BEHAVIORAL_EFFECTS:
        return 1.0, metric, None
    if raw is None:
        # A behavior can still be a valid team utility, but never invent a numeric bonus.
        return None, metric, "效果量未结构化，未计入数值排序"
    number = abs(float(raw))
    return number, metric, None


def as_values(value: Any) -> set[str]:
    if isinstance(value, list):
        return {str(item) for item in value}
    if isinstance(value, set):
        return {str(item) for item in value}
    return {str(value)} if value not in (None, "", False) else set()


def has_expected(value: Any, actual: Any) -> bool:
    expected = as_values(value)
    if not expected:
        return True
    return str(actual) in expected


def temperature_matches(text: str, temperature: float) -> bool:
    normalized = text.replace("℃", "C").replace(" ", "")
    if normalized.startswith(">="):
        return temperature >= float(normalized[2:].removesuffix("C"))
    if normalized.startswith("<="):
        return temperature <= float(normalized[2:].removesuffix("C"))
    if "-" in normalized and normalized.endswith("C"):
        low, high = normalized[:-1].split("-", 1)
        return float(low) <= temperature <= float(high)
    return False


def allowed_formation_attributes(profile: dict[str, Any]) -> set[str]:
    """Extract only the explicit cool/heat/eco set from an already-structured formation flag."""
    source = profile["component"].get("source") or {}
    text = " ".join(str(source.get(key) or "") for key in ("condition_raw", "remarks_raw"))
    return {attribute for attribute in ("cool", "heat", "eco") if attribute in text}


def disabled_target_matches(target: str, opponent_attribute: str | None) -> tuple[bool | None, str | None]:
    """Return None only when the detail fact requires an omitted opponent attribute."""
    attributes = [attribute for attribute in ("cool", "heat", "eco") if attribute in target]
    if not attributes:
        return True, None
    if opponent_attribute is None:
        return None, "缺少条件：opponent_attribute"
    if "以外" in target:
        return opponent_attribute not in attributes, "对手属性不在无效化目标范围"
    return opponent_attribute in attributes, "对手属性不属于无效化目标"


def position_map(context: dict[str, Any]) -> dict[str, int]:
    raw = context.get("member_positions") or {}
    if not isinstance(raw, dict):
        return {}
    return {str(denko_id): int(position) for denko_id, position in raw.items() if isinstance(position, int) and 1 <= position <= 6}


def relative_position_matches(profile: dict[str, Any], context: dict[str, Any], main: str, holder: str) -> tuple[bool, str | None]:
    positions = position_map(context)
    if main not in positions or holder not in positions:
        return False, "缺少主力或技能持有者的车位"
    main_position = positions[main]
    holder_position = positions[holder]
    filters = profile["component"].get("target_filters") or {}
    relation = filters.get("position_relative_to_self") or filters.get("relative_position")
    matched = {
        "previous_car": main_position == holder_position - 1,
        "one_car_before_self": main_position == holder_position - 1,
        "next_car": main_position == holder_position + 1,
        "before": main_position < holder_position,
    }.get(str(relation))
    if matched is None:
        return False, "相对车位规则未结构化"
    return matched, None if matched else "主力不在该技能要求的相对车位"


def recipient_applies(profile: dict[str, Any], request: dict[str, Any], member_ids: set[str]) -> tuple[bool, str | None]:
    component = profile["component"]
    holder = profile["denko"]["denko_id"]
    main = request["main_denko_id"]
    scene = request["scene"]
    context = request.get("context") or {}
    recipients = set(component.get("recipient") or [])
    if not recipients:
        return False, "受益对象未解析"
    if recipients <= {"self"}:
        return (holder == main, None if holder == main else "仅作用于自身，不能强化固定主力")
    if "own_skill_effects" in recipients and holder != main:
        return False, "只操作持有者自身技能，第一版不假设跨角色联动"
    if component.get("effect_kind") in {"atk_debuff", "def_debuff", "ap_debuff"} and recipients & {"self", "team_all", "own_team"}:
        return False, "己方能力下降属于代价，不作为主力增益"
    if recipients & {"team_all", "own_team", "master", "master_account"}:
        return True, None
    if recipients & {"opponent_denko", "opponent_team"}:
        if scene not in {"capture", "mechanism"}:
            return False, "当前场景不以对手妨害计分"
        actor = component.get("trigger_actor")
        if holder == main or actor == "any_team_member":
            return True, None
        if profile["activation"].get("mode") == "manual" and context.get("allow_manual_activation", False):
            return True, None
        return False, "该对手效果由持有者自身触发，不能直接强化固定主力"
    if recipients & {"accessing_denko"}:
        return (bool(context.get("assume_main_access", scene == "capture")), "未确认主力处于访问方")
    if recipients & {"accessed_denko"}:
        return (bool(context.get("assume_main_accessed", scene == "defense")), "未确认主力处于被访问方")
    if recipients & {"front_car", "own_front_car"}:
        positions = position_map(context)
        if positions:
            holder_position = positions.get(holder)
            main_position = positions.get(main)
            rule = (component.get("target_filters") or {}).get("position_rule")
            if rule == "front_car_or_second_if_self_front" and holder_position is not None and main_position is not None:
                target_position = 2 if holder_position == 1 else 1
                return main_position == target_position, "主力不在该先头/次车位规则的目标位置"
            return main_position == 1, "主力不在先头车"
        return (context.get("main_position", "front") == "front", "未确认主力位于先头车")
    if "relative_car" in recipients:
        return relative_position_matches(profile, context, main, holder)
    return False, "受益对象尚未支持"


def check_constraints(
    profile: dict[str, Any],
    request: dict[str, Any],
    members: list[dict[str, Any]],
    *,
    include_formation: bool = True,
) -> tuple[bool, list[str]]:
    filters = profile["component"].get("target_filters") or {}
    context = request.get("context") or {}
    main = next(member for member in members if member["denko_id"] == request["main_denko_id"])
    all_attributes = {member.get("attribute") for member in members if member.get("attribute")}
    reasons: list[str] = []
    pending: list[str] = []

    def require(key: str, actual: Any) -> None:
        if key not in filters:
            return
        expected = filters[key]
        if actual is None:
            pending.append(f"缺少条件：{key}")
        elif not has_expected(expected, actual):
            reasons.append(f"不满足{key}")

    require("attribute", main.get("attribute"))
    require("attributes", main.get("attribute"))
    require("type", main.get("type"))
    if "own_access_attribute" in filters:
        actual_accessor = context.get("accessing_attribute")
        recipients = set(profile["component"].get("recipient") or [])
        if actual_accessor is None and "accessing_denko" in recipients and context.get("assume_main_access", request["scene"] == "capture"):
            actual_accessor = main.get("attribute")
        require("own_access_attribute", actual_accessor)
    require("station_attribute", context.get("station_attribute"))
    require("opponent_attribute", context.get("opponent_attribute"))
    require("opponent_type", context.get("opponent_type"))
    require("opponent_pool_in", context.get("opponent_pool"))
    if "opponent_attribute_excluded" in filters and context.get("opponent_attribute") is not None and has_expected(filters["opponent_attribute_excluded"], context["opponent_attribute"]):
        reasons.append("对手属性属于排除范围")
    if "opponent_pool_excludes" in filters and context.get("opponent_pool") is not None and has_expected(filters["opponent_pool_excludes"], context["opponent_pool"]):
        reasons.append("对手系列属于排除范围")
    require("weather", context.get("weather"))
    require("weekday", context.get("weekday"))
    if "temperature_min_c" in filters:
        actual = context.get("temperature_c")
        if actual is None:
            pending.append("缺少条件：temperature_c")
        elif float(actual) < float(filters["temperature_min_c"]):
            reasons.append("气温低于技能下限")
    if "temperature_max_c" in filters:
        actual = context.get("temperature_c")
        if actual is None:
            pending.append("缺少条件：temperature_c")
        elif float(actual) > float(filters["temperature_max_c"]):
            reasons.append("气温高于技能上限")
    if "temperature_band" in filters:
        actual = context.get("temperature_c")
        if actual is None:
            pending.append("缺少条件：temperature_c")
        elif not temperature_matches(str(filters["temperature_band"]), float(actual)):
            reasons.append("气温不在技能有效区间")
    if "inactive_temperature_bands" in filters:
        actual = context.get("temperature_c")
        if actual is None:
            pending.append("缺少条件：temperature_c")
        elif any(temperature_matches(str(band), float(actual)) for band in filters["inactive_temperature_bands"]):
            reasons.append("气温属于技能无效区间")
    if "season_months" in filters:
        actual = context.get("month")
        if actual is None:
            pending.append("缺少条件：month")
        elif int(actual) not in {int(month) for month in filters["season_months"]}:
            reasons.append("当前月份不在技能季节范围")
    if "time_window" in filters:
        actual = context.get("time_window")
        if actual is None:
            pending.append("缺少条件：time_window")
        elif not has_expected(filters["time_window"], actual):
            reasons.append("当前时段不在技能有效范围")
    if include_formation and "own_team_all_attribute" in filters:
        wanted = as_values(filters["own_team_all_attribute"])
        if wanted and not (len(all_attributes) == 1 and all_attributes <= wanted):
            reasons.append("编成未满足全同属性限制")
        elif not wanted and len(all_attributes) != 1:
            reasons.append("编成未满足全同属性限制")
    if include_formation and filters.get("formation_only"):
        allowed = allowed_formation_attributes(profile)
        if not allowed:
            pending.append("编成限制未提取出允许属性")
        elif any(attribute not in allowed for attribute in all_attributes):
            reasons.append("编成包含限制属性之外的でんこ")
    if include_formation and "own_team_attribute_min_count" in filters:
        expected = filters["own_team_attribute_min_count"]
        if isinstance(expected, dict) and "attribute" in expected and "min_count" in expected:
            attribute = str(expected["attribute"])
            if sum(member.get("attribute") == attribute for member in members) < int(expected["min_count"]):
                reasons.append("编成属性人数不足")
        elif isinstance(expected, dict):
            for attribute, count in expected.items():
                if sum(member.get("attribute") == attribute for member in members) < int(count):
                    reasons.append("编成属性人数不足")
                    break
        else:
            pending.append("编成属性人数规则未结构化")
    if include_formation and "formation_size_min" in filters and len(members) < int(filters["formation_size_min"]):
        reasons.append("编成车辆数不足")
    if "opponent_team_all_attribute" in filters:
        counts = context.get("opponent_attribute_counts")
        team_size = context.get("opponent_team_size")
        wanted = str(filters["opponent_team_all_attribute"])
        if not isinstance(counts, dict) or team_size is None:
            pending.append("缺少条件：opponent_attribute_counts/opponent_team_size")
        elif int(counts.get(wanted, 0)) != int(team_size):
            reasons.append("对手编成不满足全同属性")
    if "opponent_team_attribute_diversity" in filters:
        counts = context.get("opponent_attribute_counts")
        if not isinstance(counts, dict):
            pending.append("缺少条件：opponent_attribute_counts")
        elif filters["opponent_team_attribute_diversity"] == "multiple_attributes" and sum(int(value) > 0 for value in counts.values()) < 2:
            reasons.append("对手编成属性不够多样")
    if "opponent_team_attribute_min_count" in filters:
        expected = filters["opponent_team_attribute_min_count"]
        if isinstance(expected, dict) and "attribute" in expected and "min_count" in expected:
            counts = context.get("opponent_attribute_counts")
            if not isinstance(counts, dict):
                pending.append("缺少条件：opponent_attribute_counts")
            elif int(counts.get(str(expected["attribute"]), 0)) < int(expected["min_count"]):
                reasons.append("对手属性人数不足")
        else:
            pending.append("对手属性人数规则未结构化")
    if "opponent_type_count_min" in filters:
        expected = int(filters["opponent_type_count_min"])
        target_type = str(filters.get("opponent_type") or context.get("opponent_type") or "")
        counts = context.get("opponent_type_counts")
        if not target_type:
            pending.append("对手类型人数条件缺少目标类型")
        elif not isinstance(counts, dict):
            pending.append("缺少条件：opponent_type_counts")
        elif int(counts.get(target_type, 0)) < expected:
            reasons.append("对手类型人数不足")
    if "minimum_link_minutes" in filters:
        actual = context.get("link_minutes")
        if actual is None:
            pending.append("缺少条件：link_minutes")
        elif float(actual) < float(filters["minimum_link_minutes"]):
            reasons.append("link时间不足")
    if "requires_occupied_station" in filters:
        actual = context.get("station_occupied")
        if actual is None:
            pending.append("缺少条件：station_occupied")
        elif bool(actual) != bool(filters["requires_occupied_station"]):
            reasons.append("站点占用状态不符")
    if "disabled_skill_target" in filters:
        matched, reason = disabled_target_matches(str(filters["disabled_skill_target"]), context.get("opponent_attribute"))
        if matched is None:
            pending.append(str(reason))
        elif not matched:
            reasons.append(str(reason))
    if filters.get("excluded_when_footbar"):
        footbar = context.get("holder_footbar")
        if footbar is None:
            pending.append("缺少条件：holder_footbar")
        elif footbar:
            reasons.append("技能持有者处于footbar，效果不适用")
    for key, value in filters.items():
        if key not in HANDLED_FILTER_KEYS and value not in (None, "", False, [], {}):
            pending.append(f"未建模限制：{key}")
    if reasons:
        return False, reasons
    if pending:
        return False, pending
    return True, []


def component_evaluation(profile: dict[str, Any], request: dict[str, Any], members: list[dict[str, Any]]) -> dict[str, Any]:
    component = profile["component"]
    level = request.get("level", "50")
    effect_kind = component.get("effect_kind")
    evaluation = {
        "profile_id": profile["profile_id"], "denko_id": profile["denko"]["denko_id"], "denko_name": profile["denko"]["name"],
        "component_id": component["component_id"], "effect_kind": effect_kind, "recipient": component.get("recipient") or [],
        "source_url": profile["record_meta"].get("source_url"), "condition_raw": component["source"].get("condition_raw"),
        "status": "inactive", "reasons_zh": [], "metric": None, "theoretical_max": None, "expected_value": None,
        "probability_factor": None, "probability_basis": None, "warnings_zh": [],
    }
    if effect_kind not in SCENE_EFFECTS[request["scene"]] and request["scene"] != "commute":
        evaluation["reasons_zh"] = ["该效果不属于当前场景的直接贡献"]
        return evaluation
    if request["scene"] == "commute" and profile["activation"].get("mode") == "manual" and not (request.get("context") or {}).get("allow_manual_activation", False):
        evaluation["reasons_zh"] = ["通勤低操作场景默认不计手动技能"]
        return evaluation
    if profile["activation"].get("mode") == "manual" and not (request.get("context") or {}).get("allow_manual_activation", True):
        evaluation["reasons_zh"] = ["请求未允许手动发动"]
        return evaluation
    if level not in (component.get("availability") or {}).get("levels", []):
        evaluation["reasons_zh"] = ["该等级不可用或wiki未记载"]
        return evaluation
    applies, recipient_reason = recipient_applies(profile, request, {member["denko_id"] for member in members})
    if not applies:
        evaluation["reasons_zh"] = [recipient_reason or "当前主力不属于受益对象"]
        return evaluation
    constraints_ok, constraint_reasons = check_constraints(profile, request, members)
    if not constraints_ok:
        evaluation["status"] = "pending_context" if all(reason.startswith("缺少") or reason.startswith("未建模") for reason in constraint_reasons) else "inactive"
        evaluation["reasons_zh"] = constraint_reasons
        return evaluation
    value = level_value(profile, level) or {}
    if effect_kind == "score_random_modifier" and value.get("value_expected") is not None:
        evaluation.update({
            "status": "active",
            "metric": METRIC_BY_EFFECT["score_random_modifier"],
            "theoretical_max": abs(float(value.get("value_max") if value.get("value_max") is not None else value["value_expected"])),
            "expected_value": abs(float(value["value_expected"])),
            "probability_basis": "precomputed_branch_expectation",
            "warnings_zh": ["使用已结构化的分支期望值；不再二次乘发动率"],
        })
        return evaluation
    magnitude, metric, magnitude_reason = effect_magnitude(profile, level)
    if magnitude is None:
        evaluation["status"] = "active_unquantified"
        evaluation["metric"] = metric
        evaluation["reasons_zh"] = [magnitude_reason or "效果量未记载"]
        return evaluation
    factor, basis = probability_factor(profile, level)
    if factor is None:
        evaluation.update({
            "status": "active_unquantified",
            "metric": metric,
            "theoretical_max": magnitude,
            "probability_basis": basis,
            "reasons_zh": ["发动率为区间，未擅自换算期望值"],
        })
        return evaluation
    evaluation.update({"status": "active", "metric": metric, "theoretical_max": magnitude, "expected_value": round(magnitude * factor, 6), "probability_factor": factor, "probability_basis": basis})
    conflict = (component.get("target_filters") or {}).get("own_skill_conflict")
    if conflict:
        evaluation["warnings_zh"].append(f"会产生己方技能冲突：{conflict}")
    disabled_kind = (component.get("target_filters") or {}).get("disabled_skill_kind")
    if disabled_kind:
        evaluation["warnings_zh"].append(f"无效化范围：{disabled_kind}")
    return evaluation


def member_from_profile(profile: dict[str, Any]) -> dict[str, Any]:
    denko = profile["denko"]
    return {"denko_id": denko["denko_id"], "name": denko["name"], "pool": denko["pool"], "attribute": denko.get("attribute"), "type": denko.get("type"), "source_url": profile["record_meta"].get("source_url")}


def scene_relevant(profile: dict[str, Any], scene: str) -> bool:
    return profile["component"].get("effect_kind") in SCENE_EFFECTS[scene] or (scene == "commute" and any(tag.get("id") == "commute" for tag in profile.get("scene_tags") or []))


def potential_score(profile: dict[str, Any], level: str, scene: str) -> float:
    if not scene_relevant(profile, scene):
        return 0.0
    magnitude, _, _ = effect_magnitude(profile, level)
    if magnitude is None:
        return 1.0
    factor, _ = probability_factor(profile, level)
    return abs(magnitude * factor) if factor is not None else 1.0


def can_potentially_benefit_main(profile: dict[str, Any], request: dict[str, Any], main_member: dict[str, Any]) -> bool:
    """Filter only context known before formation enumeration.

    Formation-wide restrictions are deliberately left to `build_team`; known
    wrong recipients, actor/station attributes, and missing world context must
    not consume one of the bounded candidate slots.
    """
    holder = profile["denko"]["denko_id"]
    if holder == request["main_denko_id"]:
        return True
    recipients = set(profile["component"].get("recipient") or [])
    if "relative_car" in recipients and (request.get("context") or {}).get("auto_positioning", True):
        return check_constraints(profile, request, [main_member], include_formation=False)[0]
    applies, _ = recipient_applies(profile, request, {holder, request["main_denko_id"]})
    if not applies:
        return False
    own_all = (profile["component"].get("target_filters") or {}).get("own_team_all_attribute")
    if own_all and profile["denko"].get("attribute") != main_member.get("attribute"):
        return False
    constraints_ok, _ = check_constraints(profile, request, [main_member], include_formation=False)
    return constraints_ok


def candidate_pool(profiles: list[dict[str, Any]], request: dict[str, Any]) -> tuple[list[str], dict[str, dict[str, Any]]]:
    by_denko: dict[str, dict[str, Any]] = {}
    scores: dict[str, float] = defaultdict(float)
    main = request["main_denko_id"]
    allowed = set(request.get("allowed_denko_ids") or [])
    excluded = set(request.get("excluded_denko_ids") or [])
    for profile in profiles:
        denko_id = profile["denko"]["denko_id"]
        by_denko.setdefault(denko_id, member_from_profile(profile))
    main_member = by_denko[main]
    for profile in profiles:
        denko_id = profile["denko"]["denko_id"]
        if denko_id == main or denko_id in excluded or (allowed and denko_id not in allowed):
            continue
        if can_potentially_benefit_main(profile, request, main_member):
            scores[denko_id] += potential_score(profile, request.get("level", "50"), request["scene"])
    ordered = sorted((denko_id for denko_id, score in scores.items() if score > 0), key=lambda denko_id: (-scores[denko_id], denko_id))
    # A fixed upper bound makes search predictable. Effects that only become useful after
    # composition expansion are still retained if their raw scene contribution is nonzero.
    return ordered[:14], by_denko


def metrics_from_evaluations(evaluations: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    maximum: dict[str, float] = defaultdict(float)
    expected: dict[str, float] = defaultdict(float)
    for item in evaluations:
        if item["status"] != "active" or not item.get("metric"):
            continue
        maximum[item["metric"]] += float(item["theoretical_max"])
        expected[item["metric"]] += float(item["expected_value"])
    return {
        "theoretical_max": {key: round(value, 6) for key, value in sorted(maximum.items())},
        "expected_value": {key: round(value, 6) for key, value in sorted(expected.items())},
    }


def cost_count(evaluations: list[dict[str, Any]], profiles_by_id: dict[str, dict[str, Any]]) -> int:
    costs: set[tuple[str, str]] = set()
    for item in evaluations:
        if item["status"] not in {"active", "active_unquantified"}:
            continue
        for cost in profiles_by_id[item["profile_id"]]["constraints"].get("opportunity_costs") or []:
            costs.add((item["profile_id"], cost))
    return len(costs)


def dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    left_metrics = left["metrics"]["expected_value"]
    right_metrics = right["metrics"]["expected_value"]
    keys = set(left_metrics) | set(right_metrics)
    left_inactive = left["constraints_check"]["inactive_or_pending_count"]
    right_inactive = right["constraints_check"]["inactive_or_pending_count"]
    no_worse = all(left_metrics.get(key, 0.0) >= right_metrics.get(key, 0.0) for key in keys) and left["operation_cost"] <= right["operation_cost"] and left_inactive <= right_inactive
    better = any(left_metrics.get(key, 0.0) > right_metrics.get(key, 0.0) for key in keys) or left["operation_cost"] < right["operation_cost"] or left_inactive < right_inactive
    return no_worse and better


def is_position_sensitive(profile: dict[str, Any]) -> bool:
    recipients = set(profile["component"].get("recipient") or [])
    filters = profile["component"].get("target_filters") or {}
    return bool(recipients & {"relative_car", "front_car", "own_front_car"}) or bool(filters.get("position_relative_to_self") or filters.get("relative_position") or filters.get("position_rule"))


def position_variants(member_ids: tuple[str, ...], request: dict[str, Any]) -> list[dict[str, int]]:
    """Enumerate only the at-most-six in-team positions, respecting explicit choices."""
    context = request.get("context") or {}
    slots = list(range(1, len(member_ids) + 1))
    fixed = {denko_id: position for denko_id, position in position_map(context).items() if denko_id in member_ids}
    if len(set(fixed.values())) != len(fixed) or any(position not in slots for position in fixed.values()):
        raise ValueError("member_positions must be unique positions inside the selected team size")
    main = request["main_denko_id"]
    if main not in fixed:
        main_mode = context.get("main_position", "front")
        if main_mode == "front":
            main_options = [1]
        elif main_mode == "non_front":
            main_options = [position for position in slots if position != 1]
        else:
            main_options = slots
    else:
        main_options = [fixed[main]]
    variants: list[dict[str, int]] = []
    for main_position in main_options:
        if main in fixed and fixed[main] != main_position:
            continue
        base = {**fixed, main: main_position}
        if len(set(base.values())) != len(base):
            continue
        unplaced = [denko_id for denko_id in member_ids if denko_id not in base]
        free = [position for position in slots if position not in base.values()]
        for positions in itertools.permutations(free, len(unplaced)):
            variants.append({**base, **dict(zip(unplaced, positions))})
    return variants or [{main: 1}]


def evaluations_for_best_positions(
    member_ids: tuple[str, ...],
    members: list[dict[str, Any]],
    relevant: list[dict[str, Any]],
    request: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, int], dict[str, Any]]:
    has_position_conditions = any(is_position_sensitive(profile) for profile in relevant)
    if not has_position_conditions:
        positions = position_map(request.get("context") or {}) or {request["main_denko_id"]: 1}
        return [component_evaluation(profile, request, members) for profile in relevant], positions, request
    if not (request.get("context") or {}).get("auto_positioning", True) and not position_map(request.get("context") or {}):
        return [component_evaluation(profile, request, members) for profile in relevant], {}, request
    best: tuple[tuple[float, ...], list[dict[str, Any]], dict[str, int], dict[str, Any]] | None = None
    for positions in position_variants(member_ids, request):
        positioned_request = copy.deepcopy(request)
        positioned_context = positioned_request.setdefault("context", {})
        positioned_context["member_positions"] = positions
        positioned_context["main_position"] = "front" if positions.get(request["main_denko_id"]) == 1 else "non_front"
        evaluations = [component_evaluation(profile, positioned_request, members) for profile in relevant]
        active = [item for item in evaluations if item["status"] in {"active", "active_unquantified"}]
        quantified = [item for item in active if item["status"] == "active"]
        pending = sum(item["status"] == "pending_context" for item in evaluations)
        expected = sum(float(item.get("expected_value") or 0.0) for item in quantified)
        # Position choice is not a global team score: prioritize satisfied components,
        # then known numeric contributions, then fewer unresolved position conditions.
        key = (float(len(active)), float(len(quantified)), expected, float(-pending))
        candidate = (key, evaluations, positions, positioned_request)
        if best is None or candidate[0] > best[0] or (candidate[0] == best[0] and sorted(candidate[2].items()) < sorted(best[2].items())):
            best = candidate
    assert best is not None
    return best[1], best[2], best[3]


def build_team(member_ids: tuple[str, ...], profiles_by_denko: dict[str, list[dict[str, Any]]], members_by_id: dict[str, dict[str, Any]], request: dict[str, Any], profiles_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    members = [members_by_id[denko_id] for denko_id in member_ids]
    relevant = [profile for denko_id in member_ids for profile in profiles_by_denko[denko_id] if scene_relevant(profile, request["scene"])]
    evaluations, positions, positioned_request = evaluations_for_best_positions(member_ids, members, relevant, request)
    active = [item for item in evaluations if item["status"] in {"active", "active_unquantified"}]
    inactive = [item for item in evaluations if item["status"] not in {"active", "active_unquantified"}]
    metrics = metrics_from_evaluations(evaluations)
    return {
        "team_id": hashlib.sha256("|".join(member_ids).encode("utf-8")).hexdigest()[:12],
        "members": [{**member, "position": positions.get(member["denko_id"])} for member in members],
        "metrics": metrics,
        "operation_cost": cost_count(evaluations, profiles_by_id),
        "active_components": active,
        "inactive_components": inactive[:40],
        "constraints_check": {
            "active_count": len(active),
            "inactive_or_pending_count": len(inactive),
            "team_attributes": sorted({member["attribute"] for member in members if member.get("attribute")}),
            "all_constraints_confirmed": not any(item["status"] == "pending_context" for item in evaluations),
            "positioning": {
                "mode": "auto_optimized" if positioned_request is not request else "input_or_not_needed",
                "member_positions": positions,
            },
        },
    }


def solve(request: dict[str, Any], profiles: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    validate(request, REQUEST_SCHEMA)
    using_fixture = profiles is not None
    profiles = profiles if profiles is not None else read_jsonl(PROFILES_PATH)
    profiles_by_denko: dict[str, list[dict[str, Any]]] = defaultdict(list)
    profiles_by_id: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        profiles_by_denko[profile["denko"]["denko_id"]].append(profile)
        profiles_by_id[profile["profile_id"]] = profile
    if request["main_denko_id"] not in profiles_by_denko:
        raise ValueError(f"main_denko_id not found: {request['main_denko_id']}")
    candidate_ids, members_by_id = candidate_pool(profiles, request)
    main = request["main_denko_id"]
    needed = max(0, int(request.get("slots", 6)) - 1)
    choice_size = min(needed, len(candidate_ids))
    choices = itertools.combinations(candidate_ids, choice_size)
    teams = [build_team((main, *choice), profiles_by_denko, members_by_id, request, profiles_by_id) for choice in choices]
    if not teams:
        teams = [build_team((main,), profiles_by_denko, members_by_id, request, profiles_by_id)]
    frontier = [team for team in teams if not any(other["team_id"] != team["team_id"] and dominates(other, team) for other in teams)]
    frontier.sort(key=lambda team: (-sum(team["metrics"]["expected_value"].values()), team["operation_cost"], team["team_id"]))
    result = {
        "result_version": "solver_result.v1",
        "result_meta": {
            "source_profiles_hash": "in_memory_fixture" if using_fixture else sha256(PROFILES_PATH),
            "generated_at": datetime.now(JST).isoformat(),
            "solver_version": SOLVER_VERSION,
            "cache_key": hashlib.sha256(json.dumps(request, ensure_ascii=True, sort_keys=True).encode("utf-8") + (b"fixture" if using_fixture else sha256(PROFILES_PATH).encode("ascii"))).hexdigest(),
            "limitations_zh": [
                "只把已由输入确认的条件效果计入数值；未提供的天气、对手或复杂编成条件保留为待确认。",
                "不同量纲不会折算为虚假的总伤害；表中只并列展示各自的理论最大与概率期望。",
                "第一版仅评估辅助对固定主力的直接贡献；跨角色技能联动、装备与站点全局状态仍需后续场景模型。",
            ],
        },
        "request": request,
        "candidate_summary": {"candidate_pool_size": len(candidate_ids), "enumerated_team_count": len(teams), "pareto_team_count": len(frontier)},
        "teams": frontier[:10],
    }
    validate(result, RESULT_SCHEMA)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Step4 constrained team solver")
    parser.add_argument("request", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = solve(read_json(args.request))
    write_json(args.output, result)
    print(json.dumps({"output": str(args.output), "teams": len(result["teams"]), "cache_key": result["result_meta"]["cache_key"]}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
