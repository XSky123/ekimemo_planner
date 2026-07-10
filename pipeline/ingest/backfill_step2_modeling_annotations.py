from __future__ import annotations

import argparse
import copy
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RECORD_DIR = ROOT / "data" / "records"
SOURCE_GLOB = "*_skill_facts.jsonl"
BACKFILL_VERSION = "step2_modeling_annotations.v1"
REASON = "stable_step2_modeling_review"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def component_by_id(row: dict[str, Any], component_id: str) -> dict[str, Any] | None:
    for component in row.get("skill_components") or []:
        if component.get("component_id") == component_id:
            return component
    return None


def values(component: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return component.setdefault("values_by_denko_level", {})


def mark_component(component: dict[str, Any], patch_id: str) -> None:
    component.setdefault("manual_patch_ids", [])
    if patch_id not in component["manual_patch_ids"]:
        component["manual_patch_ids"].append(patch_id)
    reasons = component.setdefault("review_reasons", [])
    if "manual_verified_stable" not in reasons:
        reasons.append("manual_verified_stable")
    component["db_backfill_lock"] = True
    component["db_backfill_reason"] = REASON
    component["db_backfill_version"] = BACKFILL_VERSION


def set_tag(component: dict[str, Any], *tags: str) -> bool:
    existing = list(component.get("modeling_tags") or [])
    changed = False
    for tag in tags:
        if tag not in existing:
            existing.append(tag)
            changed = True
    if changed:
        component["modeling_tags"] = existing
    return changed


def update_dict(component: dict[str, Any], key: str, updates: dict[str, Any]) -> bool:
    container = component.setdefault(key, {})
    changed = False
    for item_key, item_value in updates.items():
        if container.get(item_key) != item_value:
            container[item_key] = item_value
            changed = True
    return changed


def mark_values_report_ignore(component: dict[str, Any], source: str) -> int:
    changed = 0
    for value in (component.get("values_by_denko_level") or {}).values():
        if value.get("unit") == "report_ignore":
            continue
        value["unit"] = "report_ignore"
        value["db_backfilled_from"] = source
        value["db_backfill_reason"] = REASON
        value["db_backfill_version"] = BACKFILL_VERSION
        changed += 1
    return changed


def parse_raw_effect_number(value: dict[str, Any], label: str, unit: str, prefix: str | None = None) -> bool:
    raw_row = value.get("raw_row") or {}
    effect = str(raw_row.get("効果") or "")
    match = re.search(re.escape(label) + r"\s*([+-]?\d+(?:\.\d+)?)\s*[%％]?", effect)
    if not match:
        return False
    number = float(match.group(1))
    updates = {
        "unit": unit,
        "value_numeric": number,
        "value_raw": f"{prefix or label} {number:g}{'%' if unit == 'percent' else ''}",
        "db_backfilled_from": "raw_row_effect_number",
        "db_backfill_reason": REASON,
        "db_backfill_version": BACKFILL_VERSION,
    }
    changed = False
    for key, item in updates.items():
        if value.get(key) != item:
            value[key] = item
            changed = True
    return changed


def parse_percent_pair(raw: str) -> tuple[float | None, float | None]:
    match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*[%％]\s*or\s*([+-]?\d+(?:\.\d+)?)\s*[%％]", raw)
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def parse_score_probability(raw: str) -> tuple[float | None, float | None]:
    match = re.search(r"スコア\s*増加\s*(\d+(?:\.\d+)?)\s*[%％]\s*/\s*減少\s*(\d+(?:\.\d+)?)\s*[%％]", raw)
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def backfill_momiji(row: dict[str, Any]) -> int:
    component = component_by_id(row, "atk_buff")
    if not component:
        return 0
    changed = 0
    changed += update_dict(
        component,
        "scaling_conditions",
        {
            "basis": "opponent_team_type_count",
            "count_min": 1,
            "count_max": 4,
            "per_unit_source": "効果 (タイプ数=1～4)",
        },
    )
    changed += set_tag(component, "opponent_type_count_scaled_self_atk")
    for value in values(component).values():
        numeric = value.get("value_numeric")
        if isinstance(numeric, (int, float)):
            expected = {
                "unit": "percent_per_opponent_type",
                "value_min": float(numeric),
                "value_max": float(numeric) * 4,
                "db_backfilled_from": "detail_effect_header_type_count_range",
                "db_backfill_reason": REASON,
                "db_backfill_version": BACKFILL_VERSION,
            }
            for key, item in expected.items():
                if value.get(key) != item:
                    value[key] = item
                    changed += 1
    if changed:
        mark_component(component, "step2_momiji_type_count_range")
    return changed


def backfill_naru(row: dict[str, Any]) -> int:
    score_component = component_by_id(row, "score_random_modifier_1")
    atk_component = component_by_id(row, "atk_buff_2")
    if not score_component or not atk_component:
        return 0
    changed = 0
    changed += update_dict(score_component, "target_filters", {"exclude_other_skill_score": True})
    changed += set_tag(score_component, "random_score_modifier", "probability_weighted_expected_score")
    score_values = values(score_component)
    for level, atk_value in values(atk_component).items():
        raw_row = atk_value.get("raw_row") or {}
        effect_raw = str(raw_row.get("効果") or "")
        probability_raw = str(raw_row.get("発動率") or "")
        increase, decrease = parse_percent_pair(effect_raw)
        inc_prob, dec_prob = parse_score_probability(probability_raw)
        if None in {increase, decrease, inc_prob, dec_prob}:
            continue
        expected_percent = increase * inc_prob / 100 + decrease * dec_prob / 100
        current = score_values.get(str(level), {})
        new_value = {
            **current,
            "cooldown": atk_value.get("cooldown"),
            "duration": atk_value.get("duration"),
            "probability": {
                "score_increase_probability": f"{inc_prob:g}%",
                "score_decrease_probability": f"{dec_prob:g}%",
            },
            "raw_row": raw_row,
            "skill_level": atk_value.get("skill_level"),
            "source_text": atk_value.get("source_text"),
            "unit": "score_random_percent",
            "value_min": float(decrease),
            "value_max": float(increase),
            "value_expected": round(expected_percent, 6),
            "value_expected_multiplier": round(1 + expected_percent / 100, 6),
            "value_raw": f"スコア増減 +{increase:g}% or {decrease:g}%",
            "db_backfilled_from": "detail_score_random_modifier_probability",
            "db_backfill_reason": REASON,
            "db_backfill_version": BACKFILL_VERSION,
        }
        if current != new_value:
            score_values[str(level)] = new_value
            changed += 1
    if changed:
        mark_component(score_component, "step2_naru_probability_weighted_score")
    return changed


def backfill_temperature_bands(row: dict[str, Any]) -> int:
    specs = {
        "atk_buff_1": {"temperature_band": ">=30C", "temperature_min_c": 30, "inactive_temperature_bands": ["26-29C", "11-14C"]},
        "def_debuff_1": {"temperature_band": ">=30C", "temperature_min_c": 30, "inactive_temperature_bands": ["26-29C", "11-14C"]},
        "atk_buff_2": {"temperature_band": "15-25C", "temperature_min_c": 15, "temperature_max_c": 25, "inactive_temperature_bands": ["26-29C", "11-14C"]},
        "def_buff_2": {"temperature_band": "15-25C", "temperature_min_c": 15, "temperature_max_c": 25, "inactive_temperature_bands": ["26-29C", "11-14C"]},
        "atk_debuff_3": {"temperature_band": "<=10C", "temperature_max_c": 10, "inactive_temperature_bands": ["26-29C", "11-14C"]},
        "def_buff_3": {"temperature_band": "<=10C", "temperature_max_c": 10, "inactive_temperature_bands": ["26-29C", "11-14C"]},
    }
    changed = 0
    for component_id, filters in specs.items():
        component = component_by_id(row, component_id)
        if not component:
            continue
        changed += update_dict(component, "target_filters", filters)
        changed += set_tag(component, "temperature_conditional", "weather_temperature_band")
        if changed:
            mark_component(component, "step2_mizore_temperature_bands")
    return changed


def backfill_attribute_skill_disable(row: dict[str, Any]) -> int:
    component = component_by_id(row, "skill_disable")
    if not component:
        return 0
    denko_id = row.get("denko_id")
    attrs = {"extra:002": "eco", "extra:003": "heat", "extra:004": "cool"}
    attribute = attrs.get(str(denko_id))
    if not attribute:
        return 0
    changed = update_dict(
        component,
        "target_filters",
        {
            "attribute": attribute,
            "disabled_skill_kind": "attribute_skill_nullification",
            "own_skill_conflict": f"disables_own_{attribute}_skills",
        },
    )
    if component.get("target_scope") != ["opponent_team", "own_team"]:
        component["target_scope"] = ["opponent_team", "own_team"]
        changed += 1
    changed += set_tag(component, "attribute_skill_nullification", "offensive_skill_interference")
    if changed:
        mark_component(component, "step2_attribute_skill_nullification")
    return changed


def backfill_nullification_semantics(row: dict[str, Any]) -> int:
    denko_id = str(row.get("denko_id") or "")
    changed = 0

    def assign(component: dict[str, Any], key: str, value: Any) -> None:
        nonlocal changed
        if component.get(key) != value:
            component[key] = value
            changed += 1

    def mark_self_penalty(component_id: str, scope: list[str], patch_id: str) -> None:
        nonlocal changed
        component = component_by_id(row, component_id)
        if not component:
            return
        assign(component, "target_scope", scope)
        changed += set_tag(component, "self_penalty", "not_nullification_tool")
        mark_component(component, patch_id)

    self_penalties = {
        "original:065": ("skill_disable", ["own_team"], "step2_hibiki_own_supporter_disable_penalty"),
        "original:139": ("battery_disable_3", ["self"], "step2_mayaka_self_battery_disable_penalty"),
        "original:149": ("skill_force_end_2", ["self"], "step2_harukaze_self_skill_end_penalty"),
        "extra:022": ("skill_force_end_1", ["own_team"], "step2_leila_own_team_skill_end"),
        "extra:074": ("skill_force_end_3", ["own_team"], "step2_suwai_own_team_skill_end"),
        "extra:103": ("skill_force_end_2", ["own_team"], "step2_aila_own_team_skill_end"),
        "extra:113": ("skill_force_end_2", ["self"], "step2_sasara_own_skill_lifecycle_end"),
    }
    penalty_spec = self_penalties.get(denko_id)
    if penalty_spec:
        mark_self_penalty(*penalty_spec)

    if denko_id == "original:050":
        penalty = component_by_id(row, "battery_disable_2")
        if penalty:
            vu_values = {
                level: copy.deepcopy(value)
                for level, value in (penalty.get("values_by_denko_level") or {}).items()
                if level in {"92", "96", "100"}
            }
            assign(penalty, "condition_raw", "スキル発動中、自身にバッテリー使用不可")
            assign(penalty, "target_scope", ["self"])
            for value in (penalty.get("values_by_denko_level") or {}).values():
                for key, item in {
                    "unit": "condition_only",
                    "value_numeric": None,
                    "value_raw": "自身にバッテリー使用不可",
                }.items():
                    if value.get(key) != item:
                        value[key] = item
                        changed += 1
            changed += set_tag(penalty, "self_penalty", "not_nullification_tool")
            mark_component(penalty, "step2_naho_self_battery_disable_penalty")

            nullification = component_by_id(row, "damage_nullification_2")
            if not nullification:
                nullification = {
                    "activation_type": penalty.get("activation_type"),
                    "availability": {"levels": ["92", "96", "100"], "vu_only": True},
                    "component_id": "damage_nullification_2",
                    "condition_label": "(2)",
                    "condition_raw": "被ダメージが一定値以下のとき、自身が受けるダメージを無効化",
                    "confidence": "high",
                    "effect_kind": "damage_nullification",
                    "effect_role": "supplemental_effect",
                    "needs_review": False,
                    "remarks_raw": "Lv.92以上で発動",
                    "review_reasons": [],
                    "scaling_conditions": {},
                    "target_filters": {"damage_threshold_by_level": True},
                    "target_scope": ["self"],
                    "trigger_conditions": {"access_direction": "passive", "event_hint": "accessed"},
                    "values_by_denko_level": {},
                }
                row.setdefault("skill_components", []).append(nullification)
                changed += 1
            for level, source_value in vu_values.items():
                raw = str(source_value.get("value_raw") or "")
                match = re.search(r"被ダメージ\s*(\d+)\s*以下", raw)
                if not match:
                    continue
                threshold = int(match.group(1))
                source_value["unit"] = "flat_damage_threshold"
                source_value["value_numeric"] = threshold
                source_value["value_raw"] = f"被ダメージ{threshold}以下を無効化"
                if (nullification.get("values_by_denko_level") or {}).get(level) != source_value:
                    nullification.setdefault("values_by_denko_level", {})[level] = source_value
                    changed += 1
            mark_component(nullification, "step2_naho_vu_damage_nullification_split")

    if denko_id == "original:040":
        component = component_by_id(row, "skill_disable_1")
        if component:
            assign(component, "target_scope", ["opponent_team", "own_team"])
            filters = component.setdefault("target_filters", {})
            if filters.pop("opponent_type", None) is not None:
                changed += 1
            changed += update_dict(
                component,
                "target_filters",
                {
                    "type": "supporter",
                    "own_skill_conflict": "disables_own_supporter_skills",
                    "requires_occupied_station": True,
                    "excluded_when_footbar": True,
                },
            )
            changed += set_tag(component, "mixed_opponent_and_own_skill_disable", "offensive_skill_interference")
            mark_component(component, "step2_haru_mixed_skill_disable_targets")

    if denko_id == "original:022":
        component = component_by_id(row, "skill_disable_1")
        if component:
            assign(component, "condition_raw", "アクセスを受けた相手でんこ自身のスキルを一部無効化")
            changed += update_dict(component, "trigger_conditions", {"access_direction": "active", "event_hint": "access"})
            mark_component(component, "step2_ren_opponent_skill_disable_condition")

    if denko_id == "original:033":
        component = component_by_id(row, "skill_disable_1")
        if component:
            assign(component, "condition_raw", "アクセスした相手でんこ自身のダメージ増加スキルを一部無効化")
            changed += update_dict(component, "trigger_conditions", {"access_direction": "passive", "event_hint": "accessed"})
            mark_component(component, "step2_area_partial_skill_disable_condition")

    if denko_id == "original:039":
        component = component_by_id(row, "damage_nullification")
        if component:
            changed += update_dict(component, "trigger_conditions", {"access_direction": "passive", "event_hint": "accessed"})
            mark_component(component, "step2_ruru_passive_access_direction")

    if denko_id == "original:061":
        component = component_by_id(row, "skill_disable_1")
        if component:
            assign(component, "target_scope", ["opponent_team", "own_team"])
            assign(component, "condition_raw", "一定時間、双方の編成内にいるサポーターのスキルを無効化")
            changed += update_dict(component, "trigger_conditions", {"access_direction": "both", "event_hint": "access_or_accessed"})
            filters = component.setdefault("target_filters", {})
            if filters.pop("opponent_type", None) is not None:
                changed += 1
            changed += update_dict(
                component,
                "target_filters",
                {
                    "type": "supporter",
                    "own_skill_conflict": "disables_own_supporter_skills",
                    "requires_occupied_station": True,
                    "excluded_when_footbar": True,
                },
            )
            probabilities = {"5": 30, "15": 35, "30": 40, "50": 55, "60": 70, "70": 85, "80": 100, "92": 100, "96": 100, "100": 100}
            for level, probability in probabilities.items():
                value = (component.get("values_by_denko_level") or {}).get(level)
                if not value:
                    continue
                expected_probability = {"activation_probability": f"{probability}%"}
                if value.get("probability") != expected_probability:
                    value["probability"] = expected_probability
                    changed += 1
                expected_duration = "15分" if level in {"5", "15", "30", "50"} else "30分"
                if value.get("duration") != expected_duration:
                    value["duration"] = expected_duration
                    changed += 1
                if value.get("cooldown") != "4時間":
                    value["cooldown"] = "4時間"
                    changed += 1
            changed += set_tag(component, "mixed_opponent_and_own_skill_disable", "offensive_skill_interference")
            mark_component(component, "step2_chitose_skill_disable_table_recovery")

    if denko_id == "extra:029":
        component = component_by_id(row, "skill_disable")
        if component:
            assign(component, "condition_raw", "フットバースでアクセスされた時にカウンターし、相手をリブートさせた場合は相手のフットバースを無効化")
            changed += update_dict(component, "trigger_conditions", {"access_direction": "passive", "event_hint": "accessed"})
            for value in (component.get("values_by_denko_level") or {}).values():
                raw_probability = str((value.get("raw_row") or {}).get("発動率") or "")
                match = re.search(r"([\d.]+)%\s*[～〜~]\s*([\d.]+)%", raw_probability)
                if not match:
                    continue
                probability = f"{match.group(1)}%-{match.group(2)}%（按对手等级）"
                if value.get("probability") != probability:
                    value["probability"] = probability
                    changed += 1
            changed += update_dict(component, "target_filters", {"probability_basis": "opponent_rank", "opponent_rank_cap": 100})
            mark_component(component, "step2_aruha_probability_range")

    if denko_id in {"extra:107", "extra:108", "extra:109"}:
        component = component_by_id(row, "skill_disable_2")
        attribute = {"extra:107": "eco", "extra:108": "heat", "extra:109": "cool"}[denko_id]
        if component:
            assign(
                component,
                "condition_raw",
                f"編成内でんこが{attribute}属性の駅でトリックスターにアクセスされた時、相手が{attribute}属性以外なら相手でんこのスキルを無効化",
            )
            filters = component.setdefault("target_filters", {})
            if filters.pop("attribute", None) is not None:
                changed += 1
            changed += update_dict(
                component,
                "target_filters",
                {
                    "station_attribute": attribute,
                    "opponent_attribute_excluded": attribute,
                    "opponent_type": "trickster",
                },
            )
            if denko_id == "extra:108":
                changed += update_dict(component, "target_filters", {"excluded_when_footbar": True})
            for value in (component.get("values_by_denko_level") or {}).values():
                probability = value.get("probability")
                if not isinstance(probability, dict) or not probability:
                    continue
                probability_value = next(iter(probability.values()))
                expected_probability = {"activation_probability": probability_value}
                if probability != expected_probability:
                    value["probability"] = expected_probability
                    changed += 1
            mark_component(component, "step2_attribute_station_opponent_skill_disable")

    if denko_id in {"extra:002", "extra:003", "extra:004"}:
        component = component_by_id(row, "skill_disable")
        attribute = {"extra:002": "eco", "extra:003": "heat", "extra:004": "cool"}[denko_id]
        if component:
            assign(component, "condition_raw", f"一定時間、双方の編成内にいる{attribute}属性でんこのスキルを無効化")
            changed += update_dict(
                component,
                "target_filters",
                {"requires_occupied_station": True, "excluded_when_footbar": True},
            )
            mark_component(component, "step2_attribute_skill_disable_condition")

    return changed


def backfill_effect_boost_semantics(row: dict[str, Any]) -> int:
    denko_id = str(row.get("denko_id") or "")
    changed = 0

    def patch_component(
        component_id: str,
        *,
        category: str | None = None,
        target_scope: list[str] | None = None,
        tags: tuple[str, ...] = (),
        filters: dict[str, Any] | None = None,
        condition_raw: str | None = None,
        remarks_raw: str | None = None,
        patch_id: str,
    ) -> None:
        nonlocal changed
        component = component_by_id(row, component_id)
        if not component:
            return
        component_changed = 0
        if target_scope is not None and component.get("target_scope") != target_scope:
            component["target_scope"] = target_scope
            component_changed += 1
        if condition_raw is not None and component.get("condition_raw") != condition_raw:
            component["condition_raw"] = condition_raw
            component_changed += 1
        if remarks_raw is not None and component.get("remarks_raw") != remarks_raw:
            component["remarks_raw"] = remarks_raw
            component_changed += 1
        filter_updates = dict(filters or {})
        if category:
            filter_updates["effect_boost_category"] = category
        component_changed += update_dict(component, "target_filters", filter_updates)
        component_changed += set_tag(component, *tags)
        if component_changed:
            mark_component(component, patch_id)
            changed += component_changed

    internal_effect_boosts = {
        "extra:017": ("effect_multiplier", ["own_skill_effects"]),
        "extra:048": ("effect_multiplier", ["self"]),
        "original:102": ("effect_multiplier", ["own_skill_effects"]),
        "original:111": ("effect_multiplier", ["own_skill_effects"]),
    }
    internal_spec = internal_effect_boosts.get(denko_id)
    if internal_spec:
        component_id, scope = internal_spec
        patch_component(
            component_id,
            target_scope=scope,
            tags=("self_skill_internal_multiplier", "not_effect_boost_tool"),
            patch_id="step2_internal_effect_multiplier_exclusion",
        )
        if denko_id == "original:102":
            patch_component(
                "vu_night_effect_multiplier",
                target_scope=["own_skill_effects"],
                tags=("self_skill_internal_multiplier", "not_effect_boost_tool"),
                patch_id="step2_internal_effect_multiplier_exclusion",
            )

    simple_specs = {
        "extra:046": ("effect_multiplier", "skill", ["team_all"]),
        "extra:047": ("film_effect_multiplier", "film", ["own_front_car"]),
        "extra:079": ("effect_multiplier", "accessory", ["self"]),
        "extra:080": ("effect_multiplier", "accessory", ["self"]),
        "extra:127": ("effect_multiplier", "skill", ["team_all"]),
        "extra:128": ("effect_multiplier", "skill", ["team_all"]),
        "original:159": ("film_series_effect_boost", "film", ["team_all"]),
    }
    simple_spec = simple_specs.get(denko_id)
    if simple_spec:
        component_id, category, scope = simple_spec
        filters = {"film_skill_effects_excluded": True} if denko_id == "extra:047" else None
        patch_component(
            component_id,
            category=category,
            target_scope=scope,
            tags=(f"{category}_effect_boost_tool",),
            filters=filters,
            patch_id=f"step2_{category}_effect_boost_classification",
        )

    accessory_specs = {
        "extra:118": "編成内のリンク保持を強化する",
        "extra:119": "編成内のリンク獲得を強化する",
        "extra:120": "編成内の経験値の獲得を補助する",
    }
    accessory_tag = accessory_specs.get(denko_id)
    if accessory_tag:
        patch_component(
            "effect_multiplier_2",
            category="accessory",
            target_scope=["team_all"],
            tags=("accessory_effect_boost_tool", "exclusive_accessory_effect_boost"),
            filters={
                "accessory_skill_tag": accessory_tag,
                "disabled_if_other_accessory_booster_in_team": True,
                "excluded_equipped_by_denko_names": ["あんず", "らいむ"],
            },
            condition_raw=f"(2)スキルタグが「{accessory_tag}」のアクセサリーの効果量を増加",
            remarks_raw=(
                "編成内に他のアクセサリー効果量増加スキルを持つでんこがいる場合、効果(2)は発動しない。"
                "あんずとらいむが装備しているアクセサリーは対象外。"
            ),
            patch_id="step2_accessory_effect_boost_condition_recovery",
        )

    return changed


def backfill_cooldown_probability_semantics(row: dict[str, Any]) -> int:
    denko_id = str(row.get("denko_id") or "")
    changed = 0

    vu_self_probability_ids = {
        "original:001",
        "original:029",
        "original:038",
        "original:040",
        "original:042",
        "original:048",
        "original:053",
        "original:060",
        "extra:014",
    }
    if denko_id in vu_self_probability_ids:
        for component in row.get("skill_components") or []:
            if component.get("effect_kind") != "activation_probability_boost":
                continue
            component_changed = 0
            if component.get("target_scope") != ["own_skill_effects"]:
                component["target_scope"] = ["own_skill_effects"]
                component_changed += 1
            component_changed += set_tag(
                component,
                "self_skill_internal_probability_boost",
                "not_cooldown_probability_tool",
            )
            if component_changed:
                mark_component(component, "step2_vu_self_probability_boost_exclusion")
                changed += component_changed

    if denko_id == "original:025":
        component = component_by_id(row, "cooldown_reset")
        if component:
            component_changed = 0
            if component.get("target_scope") != ["team_all"]:
                component["target_scope"] = ["team_all"]
                component_changed += 1
            condition = "編成内でクールダウン状態のでんこのクールタイムを0にする"
            if component.get("condition_raw") != condition:
                component["condition_raw"] = condition
                component_changed += 1
            component_changed += update_dict(component, "target_filters", {"state": "cooldown"})
            component_changed += set_tag(component, "team_cooldown_reset_tool")
            if component_changed:
                mark_component(component, "step2_urara_team_cooldown_reset_target")
                changed += component_changed

    return changed


def backfill_self_debuff_display_semantics(row: dict[str, Any]) -> int:
    if row.get("denko_id") != "original:162":
        return 0
    changed = 0
    positive_pairs = {
        "atk_buff_1": "DEF -20%",
        "def_buff_3": "ATK -20%",
    }
    for component_id, paired_debuff in positive_pairs.items():
        component = component_by_id(row, component_id)
        if not component:
            continue
        component_changed = update_dict(
            component,
            "target_filters",
            {
                "paired_self_debuff_raw": paired_debuff,
                "paired_self_debuff_display": "remark_only",
            },
        )
        if component_changed:
            mark_component(component, "step2_temperature_self_debuff_as_remark")
            changed += component_changed
    for component_id in ("def_debuff_1", "atk_debuff_3"):
        component = component_by_id(row, component_id)
        if not component:
            continue
        component_changed = set_tag(
            component,
            "self_debuff",
            "not_standalone_report_candidate",
        )
        if component_changed:
            mark_component(component, "step2_temperature_self_debuff_hidden")
            changed += component_changed
    return changed


def backfill_trigger_actor_semantics(row: dict[str, Any]) -> int:
    denko_id = str(row.get("denko_id") or "")
    changed = 0

    def patch(
        component_id: str,
        *,
        actor_scope: str,
        access_direction: str | None = None,
        event_hint: str | None = None,
        target_scope: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        condition_raw: str | None = None,
        patch_id: str,
    ) -> None:
        nonlocal changed
        component = component_by_id(row, component_id)
        if not component:
            return
        component_changed = 0
        trigger_updates: dict[str, Any] = {"actor_scope": actor_scope}
        if access_direction:
            trigger_updates["access_direction"] = access_direction
        if event_hint:
            trigger_updates["event_hint"] = event_hint
        component_changed += update_dict(component, "trigger_conditions", trigger_updates)
        if target_scope is not None and component.get("target_scope") != target_scope:
            component["target_scope"] = target_scope
            component_changed += 1
        if filters:
            component_changed += update_dict(component, "target_filters", filters)
        if condition_raw is not None and component.get("condition_raw") != condition_raw:
            component["condition_raw"] = condition_raw
            component_changed += 1
        if component_changed:
            mark_component(component, patch_id)
            changed += component_changed

    if denko_id == "extra:116":
        patch(
            "score_gain",
            actor_scope="any_team_member",
            access_direction="active",
            event_hint="link",
            target_scope=["accessing_denko"],
            filters={"weather": "sunny", "requires_link_success": True},
            condition_raw="編成内のでんこが晴れの駅にリンクした時、スコア獲得",
            patch_id="step2_ginaa_any_team_member_link_trigger",
        )
    elif denko_id == "extra:115":
        patch(
            "score_gain_1",
            actor_scope="skill_holder",
            access_direction="active",
            event_hint="access",
            patch_id="step2_aida_skill_holder_active_trigger",
        )
        patch(
            "additional_score_gain_2",
            actor_scope="skill_holder",
            access_direction="passive",
            event_hint="accessed",
            patch_id="step2_aida_skill_holder_passive_trigger",
        )
    elif denko_id == "extra:117":
        patch(
            "score_gain",
            actor_scope="any_team_member",
            access_direction="passive",
            event_hint="accessed",
            target_scope=["accessed_denko"],
            patch_id="step2_jumana_any_team_member_passive_trigger",
        )
    elif denko_id == "original:148":
        patch(
            "atk_buff",
            actor_scope="skill_holder",
            access_direction="active",
            event_hint="access",
            patch_id="step2_reo_skill_holder_weather_trigger",
        )
    elif denko_id == "original:153":
        patch(
            "exp_gain_1",
            actor_scope="any_team_member",
            access_direction="active",
            event_hint="access",
            target_scope=["accessing_denko"],
            patch_id="step2_mokuri_accessing_denko_exp_target",
        )
        patch(
            "exp_gain_2",
            actor_scope="any_team_member",
            access_direction="active",
            event_hint="access",
            target_scope=["team_all"],
            patch_id="step2_mokuri_team_weather_exp_target",
        )
    elif denko_id == "original:162":
        for component_id in (
            "atk_buff_1",
            "def_debuff_1",
            "atk_buff_2",
            "def_buff_2",
            "atk_debuff_3",
            "def_buff_3",
        ):
            patch(
                component_id,
                actor_scope="any_team_member",
                access_direction="both",
                event_hint="access_or_accessed",
                patch_id="step2_mizore_any_team_member_both_trigger",
            )

    accessing_exp_specs = {
        "original:094": ("exp_gain_1", "exp_gain_2", "exp_gain_3"),
        "original:099": ("exp_gain_1", "exp_gain_2"),
        "original:116": ("exp_gain_1", "exp_gain_2"),
        "extra:033": ("exp_gain_1", "exp_gain_2"),
    }
    for component_id in accessing_exp_specs.get(denko_id, ()):
        patch(
            component_id,
            actor_scope="any_team_member",
            access_direction="active",
            event_hint="access",
            target_scope=["accessing_denko"],
            patch_id="step2_any_team_member_accessing_denko_exp_target",
        )

    if denko_id == "extra:028":
        patch(
            "def_buff",
            actor_scope="skill_holder",
            target_scope=["self"],
            condition_raw="(1)その日の移動距離に応じてATKとDEFが増加[自身]",
            filters={"distance_basis": "today_travel_distance", "distance_cap_km": 30},
            patch_id="step2_lingfa_distance_def_condition",
        )

    return changed


def backfill_misc_tags(row: dict[str, Any]) -> int:
    denko_id = row.get("denko_id")
    changed = 0
    if denko_id == "original:033":
        component = component_by_id(row, "skill_disable_1")
        if component:
            changed += update_dict(
                component,
                "target_filters",
                {"disabled_skill_kind": "partial_damage_increase_skill_nullification"},
            )
            changed += set_tag(component, "partial_damage_increase_skill_nullification")
            if changed:
                mark_component(component, "step2_area_partial_skill_nullification")
    elif denko_id == "original:163":
        for component_id in ("score_gain_1", "additional_score_gain_2"):
            component = component_by_id(row, component_id)
            if not component:
                continue
            changed += update_dict(
                component,
                "scaling_conditions",
                {"score_model": "sustained_cumulative_heat_damage", "burst_breaker": False},
            )
            changed += set_tag(component, "soft_station_sustained_scoring", "cumulative_heat_damage")
            mark_component(component, "step2_chiwa_sustained_score_tag")
    elif denko_id == "extra:010":
        for component_id in ("atk_buff_1", "def_debuff_2"):
            component = component_by_id(row, component_id)
            if component:
                changed += set_tag(component, "burst_button", "long_cooldown", "position_shift")
                mark_component(component, "step2_ushio_burst_long_cd_tag")
    elif denko_id == "extra:013":
        for component_id in ("atk_buff", "def_buff"):
            component = component_by_id(row, component_id)
            if component:
                changed += mark_values_report_ignore(component, "raw_modifier_without_numeric_value")
                mark_component(component, "step2_hikaru_ignore_raw_modifier_without_numeric_value")
    elif denko_id == "extra:024":
        component = component_by_id(row, "damage_cap_1")
        if component:
            if component.get("target_scope") != ["team_all"]:
                component["target_scope"] = ["team_all"]
                changed += 1
            changed += update_dict(component, "target_filters", {"opponent_team_attribute_diversity": "multiple_attributes"})
            mark_component(component, "step2_amelia_damage_cap_team_target")
    elif denko_id == "extra:030":
        for component_id in ("atk_buff", "def_buff"):
            component = component_by_id(row, component_id)
            if component:
                changed += mark_values_report_ignore(component, "film_modifier_without_numeric_value")
                mark_component(component, "step2_harisha_ignore_film_modifier_without_numeric_value")
    elif denko_id == "extra:041":
        component = component_by_id(row, "reboot_2")
        if component:
            changed += mark_values_report_ignore(component, "misparsed_bonus_not_reboot_defense")
            mark_component(component, "step2_lenya_ignore_misparsed_bonus_component")
    elif denko_id == "extra:058":
        component = component_by_id(row, "hp_recovery_2")
        if component:
            if component.get("target_scope") != ["accessed_denko"]:
                component["target_scope"] = ["accessed_denko"]
                changed += 1
            for value in (component.get("values_by_denko_level") or {}).values():
                if parse_raw_effect_number(value, "HP回復", "flat_hp", "HP回復"):
                    changed += 1
            mark_component(component, "step2_ping_hp_recovery_value")
    elif denko_id == "extra:062":
        component = component_by_id(row, "damage_reduction_1")
        if component:
            if component.get("target_scope") != ["team_all"]:
                component["target_scope"] = ["team_all"]
                changed += 1
            changed += update_dict(component, "target_filters", {"same_attribute_as_self_after_change": True})
            for value in (component.get("values_by_denko_level") or {}).values():
                if parse_raw_effect_number(value, "相性効果", "percent", "相性効果"):
                    changed += 1
            mark_component(component, "step2_eiru_affinity_reduction_value")
    elif denko_id == "extra:071":
        component = component_by_id(row, "def_buff_1")
        if component:
            changed += update_dict(component, "target_filters", {"attributes": ["cool", "eco"], "formation_only": True})
            mark_component(component, "step2_lumi_formation_attribute_fill")
    elif denko_id == "extra:092":
        component = component_by_id(row, "def_buff_1")
        if component:
            changed += update_dict(component, "target_filters", {"attributes": ["heat", "cool"], "formation_only": True})
            for value in (component.get("values_by_denko_level") or {}).values():
                raw = str(value.get("value_raw") or "")
                match = re.search(r"0\s*[～〜~]\s*(\d+(?:\.\d+)?)\s*%", raw)
                if match:
                    updates = {
                        "unit": "percent_range",
                        "value_min": 0.0,
                        "value_max": float(match.group(1)),
                        "value_numeric": None,
                        "db_backfilled_from": "raw_percent_zero_range",
                        "db_backfill_reason": REASON,
                        "db_backfill_version": BACKFILL_VERSION,
                    }
                    for key, item in updates.items():
                        if value.get(key) != item:
                            value[key] = item
                            changed += 1
            mark_component(component, "step2_ariana_formation_attribute_and_range_fill")
    elif denko_id in {"extra:107", "extra:108", "extra:109"}:
        component = component_by_id(row, "skill_disable_2")
        attribute = {"extra:107": "eco", "extra:108": "heat", "extra:109": "cool"}[str(denko_id)]
        if component:
            if component.get("target_scope") != ["opponent_denko"]:
                component["target_scope"] = ["opponent_denko"]
                changed += 1
            changed += update_dict(
                component,
                "target_filters",
                {
                    "opponent_attribute_excluded": attribute,
                    "disabled_skill_target": f"{attribute}属性以外のでんこのスキル無効化",
                },
            )
            mark_component(component, "step2_attribute_excluded_opponent_skill_disable")
    elif denko_id == "extra:122":
        component = component_by_id(row, "reboot_4")
        if component:
            changed += mark_values_report_ignore(component, "cooldown_transition_not_defense_ranking")
            changed += set_tag(component, "cooldown_transition_entry", "not_defense_ranking")
            mark_component(component, "step2_marilyn_ignore_cooldown_transition_component")
    elif denko_id == "extra:094":
        component = component_by_id(row, "def_debuff")
        if component:
            changed += update_dict(
                component,
                "target_filters",
                {
                    "own_access_attribute": "heat",
                    "opponent_type": "supporter",
                    "opponent_type_count_min": 3,
                    "exclude_self": True,
                },
            )
            changed += set_tag(component, "conditional_opponent_supporter_count_def_debuff")
            mark_component(component, "step2_claudia_condition_detail")
    elif denko_id == "original:152":
        component = component_by_id(row, "def_debuff_2")
        if component:
            changed += set_tag(component, "all_heat_sustained_def_debuff_tech")
            mark_component(component, "step2_niina_all_heat_def_debuff_tag")
    elif denko_id == "original:088":
        for component in row.get("skill_components") or []:
            changed += set_tag(component, "level_breakpoint_lv80_major")
            mark_component(component, "step2_tamaki_lv80_breakpoint_tag")
    elif denko_id == "original:039":
        component = component_by_id(row, "damage_nullification")
        if component and component.get("target_scope") != ["self"]:
            component["target_scope"] = ["self"]
            changed += 1
            changed += update_dict(
                component,
                "target_filters",
                {"hp_condition": "self_hp_full_or_vu_90_percent"},
            )
            mark_component(component, "step2_ruru_self_damage_nullification_target")
    elif denko_id == "original:004":
        component = component_by_id(row, "extra_access")
        if component and component.get("target_scope") != ["self"]:
            component["target_scope"] = ["self"]
            changed += 1
            mark_component(component, "step2_miroku_self_extra_access_target")
    elif denko_id == "original:013":
        component = component_by_id(row, "def_buff_1")
        if component:
            if component.get("target_scope") != ["self"]:
                component["target_scope"] = ["self"]
                changed += 1
            trigger = component.setdefault("trigger_conditions", {})
            if trigger.get("access_direction") != "passive" or trigger.get("event_hint") != "accessed":
                trigger["access_direction"] = "passive"
                trigger["event_hint"] = "accessed"
                changed += 1
            mark_component(component, "step2_izuna_self_def_target")
    elif denko_id == "original:029":
        component = component_by_id(row, "hp_zero_1")
        if component and not component.get("condition_raw"):
            component["condition_raw"] = "相手でんこのHPを0にする"
            changed += 1
            mark_component(component, "step2_chiko_condition_text_fill")
    elif denko_id == "original:149":
        component = component_by_id(row, "reboot_2")
        if component:
            if component.get("target_scope") != ["self"]:
                component["target_scope"] = ["self"]
                changed += 1
            changed += update_dict(component, "target_filters", {"failure_result": "self_reboot_and_skill_force_end"})
            changed += update_dict(component, "trigger_conditions", {"access_direction": "active", "event_hint": "link_failed"})
            mark_component(component, "step2_harukaze_self_reboot_target")
    elif denko_id == "extra:107":
        component = component_by_id(row, "skill_disable_2")
        if component:
            if component.get("target_scope") != ["opponent_denko"]:
                component["target_scope"] = ["opponent_denko"]
                changed += 1
            changed += update_dict(
                component,
                "target_filters",
                {
                    "opponent_attribute_excluded": "eco",
                    "disabled_skill_target": "eco属性以外のでんこのスキル無効化",
                },
            )
            mark_component(component, "step2_gabriela_non_eco_opponent_skill_disable")
    elif denko_id == "extra:045":
        for component_id in ("exp_gain_1", "exp_gain_2"):
            component = component_by_id(row, component_id)
            if component:
                changed += update_dict(component, "target_filters", {"exp_source": "cat_punch"})
                changed += set_tag(component, "cat_punch_exp_boost", "item_exp_boost")
                mark_component(component, "step2_myu_cat_punch_exp_tag")
    elif denko_id == "extra:046":
        component = component_by_id(row, "effect_multiplier")
        if component:
            changed += update_dict(
                component,
                "scaling_conditions",
                {
                    "stacking_formula_with_cat_punch_exp_boost": "cat_punch_base_exp * (1 + other_exp_bonus + myu_bonus * ako_multiplier)"
                },
            )
            changed += set_tag(component, "exp_pt_effect_multiplier", "cat_punch_exp_stack_multiplier")
            mark_component(component, "step2_ako_cat_punch_stacking_formula")
        for component_id in ("exp_gain", "score_gain"):
            component = component_by_id(row, component_id)
            if component:
                changed += mark_values_report_ignore(component, "effect_multiplier_shadow_component_without_value")
                mark_component(component, "step2_ako_ignore_shadow_gain_component")
    elif denko_id == "extra:102":
        for component_id in ("exp_gain", "score_gain"):
            component = component_by_id(row, component_id)
            if component and component.get("target_scope") != ["accessed_denko"]:
                component["target_scope"] = ["accessed_denko"]
                changed += 1
                mark_component(component, "step2_laurie_accessed_denko_target")
    elif denko_id == "original:038":
        component = component_by_id(row, "hp_recovery")
        if component:
            if component.get("target_scope") != ["specific_denko"]:
                component["target_scope"] = ["specific_denko"]
                changed += 1
            changed += update_dict(component, "target_filters", {"target_denko_name": "みこと"})
            mark_component(component, "step2_kuni_mikoto_hp_recovery_target")
    elif denko_id == "original:058":
        component = component_by_id(row, "reboot_1")
        if component and component.get("target_scope") != ["opponent_denko"]:
            component["target_scope"] = ["opponent_denko"]
            changed += 1
            mark_component(component, "step2_marika_reflect_target")
    elif denko_id == "original:135":
        component = component_by_id(row, "reboot_3")
        if component and component.get("target_scope") != ["self"]:
            component["target_scope"] = ["self"]
            changed += 1
            mark_component(component, "step2_mutsumi_self_reboot_target")
    elif denko_id == "extra:026":
        component = component_by_id(row, "exp_gain")
        if component:
            if component.get("target_scope") != ["opponent_denko"]:
                component["target_scope"] = ["opponent_denko"]
                changed += 1
            changed += update_dict(component, "target_filters", {"benefits_side": "opponent", "exp_recipient": "opponent_denko"})
            changed += set_tag(component, "opponent_exp_grant", "not_own_exp_support")
            mark_component(component, "step2_tien_opponent_exp_grant")
    elif denko_id == "extra:029":
        component = component_by_id(row, "reboot_1")
        if component and component.get("target_scope") != ["opponent_denko"]:
            component["target_scope"] = ["opponent_denko"]
            changed += 1
            mark_component(component, "step2_aruha_opponent_reboot_target")
    return changed


def backfill_row(row: dict[str, Any]) -> int:
    denko_id = row.get("denko_id")
    changed = 0
    if denko_id == "original:059":
        changed += backfill_momiji(row)
    if denko_id == "original:078":
        changed += backfill_naru(row)
    if denko_id == "original:162":
        changed += backfill_temperature_bands(row)
    if denko_id in {"extra:002", "extra:003", "extra:004"}:
        changed += backfill_attribute_skill_disable(row)
    changed += backfill_nullification_semantics(row)
    changed += backfill_effect_boost_semantics(row)
    changed += backfill_cooldown_probability_semantics(row)
    changed += backfill_self_debuff_display_semantics(row)
    changed += backfill_trigger_actor_semantics(row)
    changed += backfill_misc_tags(row)
    if changed:
        postprocess = row.setdefault("record_meta", {}).setdefault("postprocess", {})
        postprocess["step2_modeling_annotations"] = {
            "version": BACKFILL_VERSION,
            "reason": REASON,
            "changed_items": changed,
        }
    return changed


def backfill_file(path: Path, dry_run: bool) -> dict[str, Any]:
    rows = read_jsonl(path)
    changed_ids: list[str] = []
    changed_total = 0
    for row in rows:
        changed = backfill_row(row)
        if changed:
            changed_ids.append(str(row.get("denko_id")))
            changed_total += changed
    if changed_ids and not dry_run:
        write_jsonl(path, rows)
    return {
        "path": str(path.relative_to(ROOT)),
        "changed_rows": len(changed_ids),
        "changed_items": changed_total,
        "denko_ids": changed_ids,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--records-dir", type=Path, default=RECORD_DIR)
    args = parser.parse_args()

    results = [backfill_file(path, args.dry_run) for path in sorted(args.records_dir.glob(SOURCE_GLOB))]
    totals = Counter()
    for result in results:
        totals["changed_rows"] += result["changed_rows"]
        totals["changed_items"] += result["changed_items"]
    print(
        json.dumps(
            {
                "dry_run": args.dry_run,
                "backfill_version": BACKFILL_VERSION,
                "changed_rows": totals["changed_rows"],
                "changed_items": totals["changed_items"],
                "files": [result for result in results if result["changed_rows"]],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
