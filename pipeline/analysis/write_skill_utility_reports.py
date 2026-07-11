from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline.analysis import write_attack_support_rankings as base


SKILL_PATH = ROOT / "data" / "step1_db" / "skill_facts.jsonl"
OUT_HTML = ROOT / "data" / "reports" / "step2_skill_utility_reports_zh.html"

REPORT_LEVELS = base.REPORT_LEVELS
DEFAULT_LEVEL = base.DEFAULT_LEVEL

TABS = {
    "nullification_passive": {
        "title": "被访问时无效化",
        "description": "被访问时保护我方的伤害无效化，或反制访问方的技能无效化。兼具访问/被访问方向的技能也会列入。",
    },
    "nullification_active": {
        "title": "访问时无效化",
        "description": "主动访问时干扰对手的技能无效化。兼具访问/被访问方向的技能也会列入。",
    },
    "skill_effect_boost": {
        "title": "技能效果量强化",
        "description": "强化其他技能效果量的配队工具。只放大自身技能内部效果的倍率不列入。",
    },
    "accessory_effect_boost": {
        "title": "饰品效果量强化",
        "description": "强化アクセサリー效果量的技能，并明确互斥、对象标签及不适用对象。",
    },
    "film_effect_boost": {
        "title": "皮肤效果量强化",
        "description": "强化フィルム本身效果量的技能；フィルム附带技能是否适用会单独注明。",
    },
    "cooldown_probability": {
        "title": "CD/概率操作",
        "description": "只收改变队友技能发动率、重置或缩短队友 CD 的技能。VU 后仅提高自身原技能发动率的内部强化不列入。",
    },
    "condition_weekday": {
        "title": "条件：星期",
        "description": "按星期拆出实际效果，等级值来自详情页的曜日副表；VU 夜间倍率已换算到对应效果。",
    },
    "condition_month": {
        "title": "条件：月份/季节",
        "description": "按四季拆出实际效果，等级值来自详情页的季节副表；wiki 未公布的 VU 特殊月倍率明确显示为未记载。",
    },
    "condition_weather_temperature": {
        "title": "条件：天气/温度",
        "description": "合并按天气或气温发动的技能，并在独立列中标明具体天气或温度区间。自身负面效果不单独列出，只附在对应正面效果的限制说明中。",
    },
    "condition_station_count": {
        "title": "远征：访问站数",
        "description": "当天、前一天或当月访问站数会改变效果量、发动率或追加效果的技能。数值型效果按区间上限与区间均值计算；单纯 link 数和 link 时间不列入。",
    },
    "condition_distance": {
        "title": "远征：移动距离",
        "description": "按当天移动距离成长，或达到指定 km 后发动追加效果的技能。理论最大取距离区间上限，期望值取区间均值再乘发动率。",
    },
    "event_access": {
        "title": "活动/访问次数",
        "description": "只收会实际产生额外访问、随机/远程访问，或增加思い出し访问次数的技能。追加、随机和远程访问属于行为效果，不显示理论最大或期望值。",
    },
    "access_range": {
        "title": "访问范围/雷达",
        "description": "扩大レーダー检知数或最大检知数等访问范围工具。与直接产生追加访问的技能分开。",
    },
}

EFFECT_LABELS = {
    **base.EFFECT_LABELS,
    "activation_probability_boost": "发动率强化",
    "additional_score_gain": "追加积分获得",
    "atk_debuff": "ATK降低",
    "battery_disable": "バッテリー不可",
    "cooldown_reduction": "CD缩短",
    "cooldown_reset": "CD解除",
    "damage_nullification": "伤害无效化",
    "damage_reduction": "伤害减轻",
    "def_buff": "DEF增加",
    "duration_extension": "持续时间延长",
    "effect_multiplier": "效果量强化",
    "exp_gain": "经验值获得",
    "extra_access": "追加访问",
    "film_effect_multiplier": "フィルム效果强化",
    "film_series_effect_boost": "フィルム系列强化",
    "footbar": "フットバース",
    "force_hp_zero": "强制HP归零",
    "link_bonus": "linkボーナス",
    "link_transfer": "link转移",
    "memory_access_station_count": "思い出し访问次数增加",
    "memory_access_time": "访问记录时间",
    "mile_gain": "mile付与",
    "random_previous_station_access": "随机访问已访问站",
    "radar_detection_range": "雷达探测范围",
    "radar_max_detection_range": "雷达最大探测范围",
    "reboot": "重启",
    "remote_station_access": "远程访问",
    "skill_disable": "技能无效化",
    "skill_effect_nullification": "技能效果量无效化",
    "skill_force_end": "技能强制结束",
    "score_gain": "积分获得",
    "station_link_transfer": "link转让",
    "today_new_station_bonus": "今日の新駅ボーナス",
}

NULLIFICATION_KINDS = {
    "battery_disable",
    "damage_nullification",
    "skill_disable",
    "skill_effect_nullification",
    "skill_force_end",
}
NULLIFICATION_TABS = {
    "nullification_passive": "passive",
    "nullification_active": "active",
}
EFFECT_BOOST_TABS = {
    "skill_effect_boost": "skill",
    "accessory_effect_boost": "accessory",
    "film_effect_boost": "film",
}
COOLDOWN_PROBABILITY_KINDS = {
    "activation_probability_boost",
    "cooldown_reduction",
    "cooldown_reset",
}
EVENT_ACCESS_KINDS = {
    "extra_access",
    "memory_access_station_count",
    "random_previous_station_access",
    "remote_station_access",
}
ACCESS_RANGE_KINDS = {"radar_detection_range", "radar_max_detection_range"}
NON_NUMERIC_ACCESS_KINDS = {
    "extra_access",
    "random_previous_station_access",
    "remote_station_access",
}

CONDITION_PATTERNS = {
    "condition_weekday": re.compile(r"曜日|月曜日|火曜日|水曜日|木曜日|金曜日|土曜日|日曜日"),
    "condition_month": re.compile(r"(?:[1-9]|1[0-2])月|季節|春|夏|秋|冬"),
    "condition_weather_temperature": re.compile(
        r"天気|晴|雨|雪|曇|気温|温度|[+-]?\d+(?:\.\d+)?\s*(?:℃|°C)"
    ),
    "condition_station_count": re.compile(
        r"(?:今日|当日|その日|前日|今月)?(?:の)?アクセス駅数|アクセスした駅数|駅へのアクセス数|アクセス数の差|アクセス\s*\d+\s*駅"
    ),
    "condition_distance": re.compile(r"移動距離|走行距離"),
}


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def compact(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def semantic_text(row: dict[str, Any], component: dict[str, Any], *, include_level_values: bool = True) -> str:
    chunks: list[str] = [
        str(row.get("effect_summary") or ""),
        str(row.get("trigger_condition") or ""),
        str(component.get("condition_raw") or ""),
        str(component.get("remarks_raw") or ""),
        json.dumps(component.get("target_filters") or {}, ensure_ascii=False),
        json.dumps(component.get("scaling_conditions") or {}, ensure_ascii=False),
        json.dumps(component.get("trigger_conditions") or {}, ensure_ascii=False),
    ]
    if include_level_values:
        for value in (component.get("values_by_denko_level") or {}).values():
            chunks.append(str(value.get("value_raw") or ""))
    return compact(" ".join(chunks))


def component_text(component: dict[str, Any], *, include_level_values: bool = True) -> str:
    chunks: list[str] = [
        str(component.get("condition_raw") or ""),
        str(component.get("remarks_raw") or ""),
        json.dumps(component.get("target_filters") or {}, ensure_ascii=False),
        json.dumps(component.get("scaling_conditions") or {}, ensure_ascii=False),
        json.dumps(component.get("trigger_conditions") or {}, ensure_ascii=False),
    ]
    if include_level_values:
        for value in (component.get("values_by_denko_level") or {}).values():
            chunks.append(str(value.get("value_raw") or ""))
    return compact(" ".join(chunks))


def condition_hit(tab_id: str, row: dict[str, Any], component: dict[str, Any]) -> bool:
    filters = component.get("target_filters") or {}
    if tab_id == "condition_weekday":
        if filters.get("weekday"):
            return True
        if any((item.get("target_filters") or {}).get("weekday") for item in row.get("skill_components") or []):
            return False
    if tab_id == "condition_month":
        if filters.get("season_months"):
            return True
        if any((item.get("target_filters") or {}).get("season_months") for item in row.get("skill_components") or []):
            return False
    pattern = CONDITION_PATTERNS[tab_id]
    if tab_id in {"condition_station_count", "condition_distance"}:
        focused_text = compact(
            " ".join(
                [
                    str(component.get("condition_raw") or ""),
                    json.dumps(component.get("target_filters") or {}, ensure_ascii=False),
                    json.dumps(component.get("scaling_conditions") or {}, ensure_ascii=False),
                ]
            )
        )
        return bool(pattern.search(focused_text))
    text = component_text(component, include_level_values=True)
    return bool(pattern.search(text))


def is_nullification_tool(component: dict[str, Any]) -> bool:
    kind = str(component.get("effect_kind") or "")
    if kind not in NULLIFICATION_KINDS:
        return False
    tags = set(component.get("modeling_tags") or [])
    if "not_nullification_tool" in tags:
        return False
    if kind == "damage_nullification":
        return True
    scopes = set(component.get("target_scope") or [])
    return bool(scopes & {"opponent_denko", "opponent_team"})


def belongs_to_tab(tab_id: str, row: dict[str, Any], component: dict[str, Any]) -> bool:
    kind = str(component.get("effect_kind") or "")
    tags = set(component.get("modeling_tags") or [])
    if "not_standalone_report_candidate" in tags:
        return False
    if tab_id in NULLIFICATION_TABS:
        if not is_nullification_tool(component):
            return False
        direction = str((component.get("trigger_conditions") or {}).get("access_direction") or "")
        return direction in {NULLIFICATION_TABS[tab_id], "both"}
    if tab_id in EFFECT_BOOST_TABS:
        if "not_effect_boost_tool" in tags:
            return False
        category = str((component.get("target_filters") or {}).get("effect_boost_category") or "")
        return category == EFFECT_BOOST_TABS[tab_id]
    if tab_id == "cooldown_probability":
        if kind not in COOLDOWN_PROBABILITY_KINDS:
            return False
        if "not_cooldown_probability_tool" in tags:
            return False
        scopes = set(component.get("target_scope") or [])
        if kind == "activation_probability_boost" and scopes <= {"self", "own_skill_effects"}:
            return False
        return True
    if tab_id == "condition_weather_temperature":
        scopes = set(component.get("target_scope") or [])
        if kind in {"atk_debuff", "def_debuff"} and scopes & {"self", "own_team", "team_all"}:
            return False
        return condition_hit(tab_id, row, component)
    if tab_id in CONDITION_PATTERNS:
        return condition_hit(tab_id, row, component)
    if tab_id == "event_access":
        return kind in EVENT_ACCESS_KINDS
    if tab_id == "access_range":
        return kind in ACCESS_RANGE_KINDS
    return False


def signed_numbers(text: str) -> list[float]:
    out = []
    for raw in re.findall(r"[+-]?\d+(?:\.\d+)?", text.replace("％", "%")):
        try:
            out.append(float(raw))
        except ValueError:
            pass
    return out


def metric_range(
    tab_id: str,
    component: dict[str, Any],
    value: dict[str, Any],
) -> tuple[float | None, float | None]:
    if tab_id in NULLIFICATION_TABS:
        return None, None
    kind = str(component.get("effect_kind") or "")
    if kind in NON_NUMERIC_ACCESS_KINDS:
        return None, None
    raw = str(value.get("value_raw") or "")
    numeric_text = raw.split("※", 1)[0]
    if "クールタイム解除" in raw or "CD解除" in raw:
        return 999.0, 999.0
    if tab_id == "cooldown_probability" and re.search(r"クールタイム|CD", raw):
        nums = signed_numbers(numeric_text)
        metric = max((abs(num) for num in nums), default=None)
        return metric, metric
    if "倍" in numeric_text:
        nums = signed_numbers(numeric_text)
        metric = max(nums) if nums else None
        return metric, metric

    # Step1 already stores most scalar ranges as value_min/value_max. Reuse the
    # attack report's range semantics so 0-55% is not collapsed to value_numeric=0.
    value_min, value_max = base.value_range(tab_id, component, value)

    # A few station-count rows retain the source formula instead of materialized
    # bounds (for example, -1.4 x n with an upper limit of 70 stations).
    formula_match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*[×x]\s*n", numeric_text, re.IGNORECASE)
    if formula_match and (value.get("value_min") is None or value.get("value_max") is None):
        condition = str(component.get("condition_raw") or "")
        upper_match = re.search(r"上限\s*(\d+(?:\.\d+)?)\s*駅", condition)
        if upper_match:
            maximum = abs(float(formula_match.group(1))) * float(upper_match.group(1))
            return 0.0, maximum
    return value_min, value_max


def level_value_text(tab_id: str, component: dict[str, Any], level: str, value: dict[str, Any]) -> str:
    raw = base.clean_display_text(value.get("value_raw") or "-")
    if tab_id in NULLIFICATION_TABS:
        kind = str(component.get("effect_kind") or "")
        technical_values = {
            "battery_disable",
            "damage_nullification",
            "skill_disable",
            "skill_force_end",
            "スキル無効化",
            "ダメージ無効化",
        }
        if kind == "damage_nullification" and value.get("unit") not in {"flat_damage_threshold", "damage_threshold"}:
            raw = EFFECT_LABELS.get(kind, kind)
        if raw in technical_values or raw == "-" or re.fullmatch(r"[\d.]+%", raw):
            raw = EFFECT_LABELS.get(kind, kind)
    return f"Lv{level}: {raw}" if level != DEFAULT_LEVEL else raw


def level_metrics(tab_id: str, component: dict[str, Any], level: str) -> dict[str, Any] | None:
    values = component.get("values_by_denko_level") or {}
    value = values.get(level)
    if not value:
        return None
    if value.get("unit") == "unrecorded":
        return {
            "level": level,
            "sort_max": None,
            "sort_avg": None,
            "value_text": level_value_text(tab_id, component, level, value),
            "max_text": "未记载",
            "avg_text": "未记载",
            "probability": utility_probability_text(value),
            "duration": value.get("duration") or "-",
            "cooldown": value.get("cooldown") or "-",
        }
    value_min, metric = metric_range(tab_id, component, value)
    average = base.mean_value(value_min, metric)
    expected = average * base.probability_factor(value) / 100 if average is not None else None
    metric_text = "-" if metric is None else f"{metric:g}"
    expected_text = "-" if expected is None else f"{expected:g}"
    return {
        "level": level,
        "sort_max": metric,
        "sort_avg": expected,
        "value_text": level_value_text(tab_id, component, level, value),
        "max_text": metric_text,
        "avg_text": expected_text,
        "probability": utility_probability_text(value),
        "duration": value.get("duration") or "-",
        "cooldown": value.get("cooldown") or "-",
    }


def target_text(component: dict[str, Any]) -> str:
    scopes = set(component.get("target_scope") or [])
    filters = component.get("target_filters") or {}
    if scopes == {"opponent_team", "own_team"}:
        if filters.get("attribute"):
            return f"双方编成内{filters['attribute']}属性でんこ"
        if filters.get("type"):
            return f"双方编成内{filters['type']}"
        return "双方编成"
    target = base.target_text(component)
    target = re.sub(r"component:[\w_]+", "关联效果", target)
    target = re.sub(r"(关联效果)(?:、关联效果)+", r"\1", target)
    return target


def utility_probability_text(value: dict[str, Any]) -> str:
    probability = value.get("probability")
    if isinstance(probability, dict):
        items = [str(item) for item in probability.values() if item not in {None, "", "-"}]
        if len(items) == 1:
            return items[0]
    return base.probability_text(value)


def utility_filter_text(component: dict[str, Any]) -> str:
    text = base.compact_filter_text(component)
    scopes = set(component.get("target_scope") or [])
    filters = component.get("target_filters") or {}
    parts = [part for part in text.split("；") if part and part != "-"]
    parts = [part for part in parts if part not in {"主动访问", "被访问"}]
    if scopes == {"opponent_team", "own_team"}:
        if filters.get("attribute"):
            parts = [part for part in parts if part != f"对象{filters['attribute']}属性"]
        if filters.get("type"):
            parts = [part for part in parts if part != f"对象类型 {filters['type']}"]
    if filters.get("accessory_skill_tag"):
        parts.append(f"对象饰品标签：{filters['accessory_skill_tag']}")
    if filters.get("disabled_if_other_accessory_booster_in_team"):
        parts.append("队内有其他饰品效果量强化技能时不发动")
    excluded_names = filters.get("excluded_equipped_by_denko_names")
    if excluded_names:
        parts.append(f"不适用于{'/'.join(map(str, excluded_names))}装备的饰品")
    if filters.get("film_skill_effects_excluded"):
        parts.append("不强化フィルム附带的技能效果")
    if filters.get("paired_self_debuff_raw"):
        parts.append(f"同时我方{filters['paired_self_debuff_raw']}")
    if filters.get("requires_link_success"):
        parts.append("必须link成功")
    if filters.get("distance_cap_km"):
        parts.append(f"移动距离上限{filters['distance_cap_km']}km")
    return "；".join(parts) if parts else "-"


def effect_label(tab_id: str, kind: str) -> str:
    labels = {
        "skill_effect_boost": "技能效果量强化",
        "accessory_effect_boost": "饰品效果量强化",
        "film_effect_boost": "皮肤效果量强化",
    }
    return labels.get(tab_id, EFFECT_LABELS.get(kind, kind))


def access_direction_text(component: dict[str, Any]) -> str:
    trigger = component.get("trigger_conditions") or {}
    direction = str(trigger.get("access_direction") or "")
    actor_scope = str(trigger.get("actor_scope") or "")
    event_hint = str(trigger.get("event_hint") or "")
    if actor_scope == "any_team_member":
        if direction == "both":
            return "队伍任意成员访问/被访问"
        if direction == "passive":
            return "队伍任意成员被访问"
        if event_hint == "link":
            return "队伍任意成员link"
        if direction == "active":
            return "队伍任意成员访问"
    if actor_scope == "skill_holder":
        if direction == "both":
            return "自己访问/被访问"
        if direction == "passive":
            return "自己被访问"
        if event_hint == "link":
            return "自己link"
        if direction == "active":
            return "自己访问"
    if actor_scope == "front_car":
        if direction == "passive":
            return "先头车被访问"
        if event_hint == "link":
            return "先头车link"
        if direction == "active":
            return "先头车访问"
    labels = {
        "active": "访问",
        "passive": "被访问",
        "both": "访问/被访问",
        "none": "非访问触发",
    }
    if direction in labels:
        return labels[direction]

    text = compact(" ".join([str(component.get("condition_raw") or ""), str(component.get("remarks_raw") or "")]))
    if re.search(r"アクセスする際.*(?:された際|アクセスされた)|アクセス時.*被アクセス", text):
        return "访问/被访问"
    if re.search(r"アクセスされた|アクセスされる|被アクセス", text):
        return "被访问"
    if re.search(r"アクセスした|アクセスする|アクセス時|チェックイン", text):
        return "访问"
    return "不限定"


def weather_temperature_text(component: dict[str, Any]) -> str:
    filters = component.get("target_filters") or {}
    band = str(filters.get("temperature_band") or "")
    if band:
        return {
            ">=30C": ">=30°C",
            "15-25C": "15-25°C",
            "<=10C": "<=10°C",
        }.get(band, band)
    text = compact(" ".join([str(component.get("condition_raw") or ""), str(component.get("remarks_raw") or "")]))
    temperature_patterns = (
        (r"30\s*(?:℃|°C)\s*以上", ">=30°C"),
        (r"15\s*(?:℃|°C)?\s*[～〜~-]\s*25\s*(?:℃|°C)", "15-25°C"),
        (r"10\s*(?:℃|°C)\s*以下", "<=10°C"),
    )
    for pattern, label in temperature_patterns:
        if re.search(pattern, text):
            return label
    weather_labels = []
    for pattern, label in ((r"晴", "晴天"), (r"雨", "雨天"), (r"曇", "阴天"), (r"雪", "雪天")):
        if re.search(pattern, text):
            weather_labels.append(label)
    return "/".join(weather_labels) if weather_labels else "-"


def condition_text(tab_id: str, row: dict[str, Any], component: dict[str, Any]) -> str:
    filters = component.get("target_filters") or {}
    if tab_id == "condition_weekday" and filters.get("weekday_raw"):
        return f"{filters['weekday_raw']}（按技能发动时的星期决定；跨日后保持发动时效果）"
    if tab_id == "condition_month" and filters.get("season_months_raw"):
        return str(filters["season_months_raw"])
    condition = base.display_condition_text(component)
    if condition:
        return condition
    return compact(row.get("trigger_condition") or row.get("effect_summary") or "-")


def build_candidates(tab_id: str, rows: list[dict[str, Any]], metadata: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    candidates = []
    for row in rows:
        denko_id = str(row.get("denko_id") or "")
        for component in row.get("skill_components") or []:
            if not belongs_to_tab(tab_id, row, component):
                continue
            levels = {
                level: metrics
                for level in REPORT_LEVELS
                if (metrics := level_metrics(tab_id, component, level)) is not None
            }
            if not levels:
                continue
            fallback_level, _fallback_value = base.basis_value(component)
            initial_level = DEFAULT_LEVEL if DEFAULT_LEVEL in levels else fallback_level if fallback_level in levels else next(iter(levels))
            initial = levels[initial_level]
            denko_meta = metadata.get(denko_id, {})
            group_id, group_label = base.activation_group(row, component)
            condition = condition_text(tab_id, row, component)
            filters = utility_filter_text(component)
            access_direction = access_direction_text(component)
            weather_condition = weather_temperature_text(component) if tab_id == "condition_weather_temperature" else "-"
            all_level_text = " ".join(str(metrics["value_text"]) for metrics in levels.values())
            search = " ".join(
                [
                    denko_id,
                    str(row.get("name") or ""),
                    str(denko_meta.get("attribute") or ""),
                    str(denko_meta.get("type_key") or ""),
                    str(component.get("effect_kind") or ""),
                    str(component.get("component_id") or ""),
                    condition,
                    access_direction,
                    weather_condition,
                    filters,
                    all_level_text,
                ]
            ).lower()
            candidates.append(
                {
                    "sort_max": initial["sort_max"],
                    "sort_avg": initial["sort_avg"],
                    "basis_level": initial_level,
                    "denko_id": denko_id,
                    "name": row.get("name"),
                    "attribute": denko_meta.get("attribute", "-"),
                    "type_key": denko_meta.get("type_key", "unknown"),
                    "kind": component.get("effect_kind") or "unknown",
                    "component_id": component.get("component_id"),
                    "condition": condition,
                    "target": target_text(component),
                    "filters": filters,
                    "activation_group": group_id,
                    "activation_label": group_label,
                    "activation_type": component.get("activation_type") or row.get("activation_type") or "",
                    "access_direction": access_direction,
                    "weather_condition": weather_condition,
                    "probability": initial["probability"],
                    "duration": initial["duration"],
                    "cooldown": initial["cooldown"],
                    "level_value": initial["value_text"],
                    "max_text": initial["max_text"],
                    "avg_text": initial["avg_text"],
                    "level_data": json.dumps(levels, ensure_ascii=False, separators=(",", ":")),
                    "vu_only": base.is_vu_only(component, fallback_level),
                    "url": row.get("detail_url") or "",
                    "search": search,
                    "calendar_order": calendar_order(tab_id, component),
                }
            )
    if tab_id in {"condition_weekday", "condition_month"}:
        candidates.sort(
            key=lambda item: (
                item["calendar_order"],
                base.denko_sort_key(str(item["denko_id"])),
                str(item["component_id"]),
            )
        )
        return candidates
    candidates.sort(
        key=lambda item: (
            -(item["sort_avg"] if item["sort_avg"] is not None else -1),
            base.denko_sort_key(str(item["denko_id"])),
            str(item["component_id"]),
        )
    )
    return candidates


def calendar_order(tab_id: str, component: dict[str, Any]) -> int:
    filters = component.get("target_filters") or {}
    if tab_id == "condition_weekday":
        return {
            "sunday": 0,
            "monday": 1,
            "tuesday": 2,
            "wednesday": 3,
            "thursday": 4,
            "friday": 5,
            "saturday": 6,
        }.get(str(filters.get("weekday") or ""), 99)
    if tab_id == "condition_month":
        component_id = str(component.get("component_id") or "")
        for index, season in enumerate(("spring", "summer", "autumn", "winter")):
            if component_id.endswith(f"_{season}"):
                return index
    return 99


def render_rows(tab_id: str, candidates: list[dict[str, Any]]) -> str:
    rows = []
    for rank, item in enumerate(candidates, 1):
        component_label = base.component_display_label(item["component_id"], item["kind"])
        component_html = (
            f'<br><span class="muted">{esc(component_label)}</span>'
            if component_label and tab_id not in {*NULLIFICATION_TABS, *EFFECT_BOOST_TABS, "condition_weekday", "condition_month"}
            else ""
        )
        filters_html = f'<br><span class="muted">{esc(item["filters"])}</span>' if item["filters"] != "-" else ""
        rows.append(
            "\n".join(
                [
                    f'<tr data-tab="{esc(tab_id)}" data-search="{esc(item["search"])}" data-activation="{esc(item["activation_group"])}" data-attr="{esc(item["attribute"])}" data-type="{esc(item["type_key"])}" data-vu-only="{str(item["vu_only"]).lower()}" data-sort-max="{item["sort_max"] if item["sort_max"] is not None else -1}" data-sort-avg="{item["sort_avg"] if item["sort_avg"] is not None else -1}" data-levels="{esc(item["level_data"])}">',
                    f'<td class="rank">{rank}</td>',
                    f'<td><strong>{esc(item["denko_id"])}</strong><br><a href="{esc(item["url"])}">{esc(item["name"])}</a></td>',
                    f'<td>{esc(item["attribute"])}</td>',
                    f'<td>{esc(item["type_key"])}</td>',
                    f'<td>{esc(effect_label(tab_id, str(item["kind"])))}{component_html}</td>',
                    f'<td class="metric max-cell utility-hidden-metric">{esc(item["max_text"])}</td>',
                    f'<td class="metric avg-cell utility-hidden-metric">{esc(item["avg_text"])}</td>',
                    f'<td class="level-cell">{esc(item["level_value"])}</td>',
                    f'<td class="probability-cell">{esc(item["probability"])}</td>',
                    f'<td class="duration-cell">{esc(item["duration"])}</td>',
                    f'<td class="cooldown-cell">{esc(item["cooldown"])}</td>',
                    f'<td title="{esc(item["activation_type"])}">{esc(item["activation_label"])}</td>',
                    f'<td class="access-direction-cell">{esc(item["access_direction"])}</td>',
                    f'<td class="weather-condition-column">{esc(item["weather_condition"])}</td>',
                    f'<td>{esc(item["target"])}{filters_html}</td>',
                    f'<td>{esc(item["condition"])}</td>',
                    "</tr>",
                ]
            )
        )
    return "".join(rows)


def render_table(tab_id: str, candidates: list[dict[str, Any]]) -> str:
    tab = TABS[tab_id]
    no_metrics_tabs = {
        *NULLIFICATION_TABS,
        *EFFECT_BOOST_TABS,
        "cooldown_probability",
        "condition_weekday",
        "condition_month",
    }
    panel_classes = []
    if tab_id in no_metrics_tabs:
        panel_classes.append("tab-no-metrics")
    if tab_id == "condition_weather_temperature":
        panel_classes.append("tab-weather")
    panel_class = "".join(f" {item}" for item in panel_classes)
    return f"""
    <section class="tab-panel{panel_class}" id="panel-{esc(tab_id)}" data-tab-panel="{esc(tab_id)}">
      <h2>{esc(tab["title"])} {base.section_count_html(candidates)}</h2>
      <p>{esc(tab["description"])}</p>
      <table>
        <thead>
          <tr>
            <th>排行</th>
            <th>でんこ</th>
            <th>属性</th>
            <th>类型</th>
            <th>效果</th>
            <th class="utility-hidden-metric">理论最大</th>
            <th class="utility-hidden-metric">期望值</th>
            <th>等级值</th>
            <th>概率</th>
            <th>持续</th>
            <th>CD</th>
            <th>发动</th>
            <th>访问方向</th>
            <th class="weather-condition-column">天气/温度</th>
            <th>对象/限制</th>
            <th>触发与条件</th>
          </tr>
        </thead>
        <tbody>{render_rows(tab_id, candidates)}</tbody>
      </table>
    </section>
    """


def audit_nullification_candidates(
    candidates_by_tab: dict[str, list[dict[str, Any]]],
    rows: list[dict[str, Any]],
) -> None:
    issues = []
    expected_keys = {
        (str(row.get("denko_id") or ""), str(component.get("component_id") or ""))
        for row in rows
        for component in row.get("skill_components") or []
        if is_nullification_tool(component)
    }
    actual_items: dict[tuple[str, str], dict[str, Any]] = {}
    for tab_id, expected_direction in NULLIFICATION_TABS.items():
        accepted_labels = {
            "passive": {"被访问", "访问/被访问", "队伍任意成员被访问", "自己被访问", "先头车被访问"},
            "active": {"访问", "访问/被访问", "队伍任意成员访问", "自己访问", "先头车访问"},
        }[expected_direction]
        for item in candidates_by_tab[tab_id]:
            key = (str(item["denko_id"]), str(item["component_id"]))
            actual_items[key] = item
            if item["access_direction"] not in accepted_labels:
                issues.append(f"{item['denko_id']}: wrong direction in {tab_id}")
    missing = expected_keys - set(actual_items)
    if missing:
        issues.append("unclassified direction: " + ",".join(f"{denko_id}/{component_id}" for denko_id, component_id in sorted(missing)))
    for item in actual_items.values():
        if item["target"] == "对象未明":
            issues.append(f"{item['denko_id']}: target unknown")
        if "発動率(" in item["probability"]:
            issues.append(f"{item['denko_id']}: numbered probability label leaked")
        if item["kind"] in {"battery_disable", "skill_force_end"} and not item["target"].startswith("对手"):
            issues.append(f"{item['denko_id']}: self penalty leaked")
    if issues:
        raise ValueError("nullification audit failed: " + "; ".join(issues))


def audit_effect_boost_candidates(candidates_by_tab: dict[str, list[dict[str, Any]]]) -> None:
    issues = []
    all_ids: set[str] = set()
    for tab_id, expected_category in EFFECT_BOOST_TABS.items():
        for item in candidates_by_tab[tab_id]:
            all_ids.add(str(item["denko_id"]))
            if item["target"] == "对象未明":
                issues.append(f"{item['denko_id']}: target unknown")
            if compact(item["condition"]).endswith(("、", ",")):
                issues.append(f"{item['denko_id']}: truncated condition")
            if effect_label(tab_id, str(item["kind"])) == str(item["kind"]):
                issues.append(f"{item['denko_id']}: untranslated effect label")
            if expected_category == "accessory" and item["denko_id"] in {"extra:118", "extra:119", "extra:120"}:
                if "有其他饰品效果量强化技能时不发动" not in item["filters"]:
                    issues.append(f"{item['denko_id']}: accessory exclusivity missing")
    leaked = all_ids & {"extra:017", "extra:048", "original:102", "original:111"}
    if leaked:
        issues.append("internal self multiplier leaked: " + ",".join(sorted(leaked)))
    if issues:
        raise ValueError("effect boost audit failed: " + "; ".join(issues))


def audit_calendar_candidates(
    candidates_by_tab: dict[str, list[dict[str, Any]]],
    rows: list[dict[str, Any]],
) -> None:
    issues = []
    specs = {
        "condition_weekday": "weekday",
        "condition_month": "season_months",
    }
    for tab_id, filter_key in specs.items():
        expected = {
            (str(row.get("denko_id") or ""), str(component.get("component_id") or ""))
            for row in rows
            for component in row.get("skill_components") or []
            if (component.get("target_filters") or {}).get(filter_key)
        }
        actual = {
            (str(item["denko_id"]), str(item["component_id"]))
            for item in candidates_by_tab[tab_id]
        }
        if actual != expected:
            missing = expected - actual
            extra = actual - expected
            if missing:
                issues.append(f"{tab_id}: missing {sorted(missing)}")
            if extra:
                issues.append(f"{tab_id}: extra {sorted(extra)}")
        for item in candidates_by_tab[tab_id]:
            if EFFECT_LABELS.get(str(item["kind"])) in {None, str(item["kind"])}:
                issues.append(f"{item['denko_id']}/{item['component_id']}: untranslated effect")
            level_data = json.loads(item["level_data"])
            value_text = " ".join(str(value.get("value_text") or "") for value in level_data.values())
            if "曜日変化" in value_text or " x倍" in value_text:
                issues.append(f"{item['denko_id']}/{item['component_id']}: unresolved auxiliary-table value")
    if issues:
        raise ValueError("calendar condition audit failed: " + "; ".join(issues))


def audit_cooldown_probability_candidates(candidates: list[dict[str, Any]]) -> None:
    issues = []
    expected_ids = {"original:025", "original:034", "extra:021", "extra:085"}
    actual_ids = {str(item["denko_id"]) for item in candidates}
    if actual_ids != expected_ids:
        issues.append(f"candidate ids mismatch: expected={sorted(expected_ids)} actual={sorted(actual_ids)}")
    for item in candidates:
        if item["target"] == "对象未明":
            issues.append(f"{item['denko_id']}: target unknown")
        if item["kind"] == "activation_probability_boost" and item["vu_only"]:
            issues.append(f"{item['denko_id']}: VU self probability boost leaked")
    urara = next((item for item in candidates if item["denko_id"] == "original:025"), None)
    if not urara or urara["target"] != "编成内全员" or "クールダウン中" not in urara["filters"]:
        issues.append("original:025 cooldown target/filter incorrect")
    if issues:
        raise ValueError("cooldown/probability audit failed: " + "; ".join(issues))


def audit_weather_temperature_candidates(candidates: list[dict[str, Any]]) -> None:
    issues = []
    false_positive_ids = {"original:142", "extra:020"}
    leaked_false_positives = false_positive_ids & {str(item["denko_id"]) for item in candidates}
    if leaked_false_positives:
        issues.append("ordinal false positives: " + ",".join(sorted(leaked_false_positives)))
    for item in candidates:
        if item["weather_condition"] == "-":
            issues.append(f"{item['denko_id']}/{item['component_id']}: weather/temperature unresolved")
        if item["kind"] in {"atk_debuff", "def_debuff"}:
            issues.append(f"{item['denko_id']}/{item['component_id']}: self debuff leaked")
        if EFFECT_LABELS.get(str(item["kind"])) in {None, str(item["kind"])}:
            issues.append(f"{item['denko_id']}/{item['component_id']}: untranslated effect")
        if item["access_direction"] in {"访问", "被访问", "访问/被访问", "不限定"}:
            issues.append(f"{item['denko_id']}/{item['component_id']}: trigger actor unresolved")
    by_component = {str(item["component_id"]): item for item in candidates if item["denko_id"] == "original:162"}
    if "同时我方DEF -20%" not in str(by_component.get("atk_buff_1", {}).get("filters") or ""):
        issues.append("original:162 high-temperature DEF debuff remark missing")
    if "同时我方ATK -20%" not in str(by_component.get("def_buff_3", {}).get("filters") or ""):
        issues.append("original:162 low-temperature ATK debuff remark missing")
    ginaa = next((item for item in candidates if item["denko_id"] == "extra:116"), None)
    if (
        not ginaa
        or ginaa["access_direction"] != "队伍任意成员link"
        or ginaa["target"] != "访问中的でんこ"
        or "必须link成功" not in ginaa["filters"]
    ):
        issues.append("extra:116 trigger actor/recipient/link requirement incorrect")
    if issues:
        raise ValueError("weather/temperature audit failed: " + "; ".join(issues))


def audit_expedition_and_access_candidates(candidates_by_tab: dict[str, list[dict[str, Any]]]) -> None:
    issues = []
    station_pattern = CONDITION_PATTERNS["condition_station_count"]
    distance_pattern = CONDITION_PATTERNS["condition_distance"]
    for item in candidates_by_tab["condition_station_count"]:
        if not station_pattern.search(str(item["condition"])):
            issues.append(f"{item['denko_id']}/{item['component_id']}: station-count condition unresolved")
    for item in candidates_by_tab["condition_distance"]:
        if not distance_pattern.search(str(item["condition"])):
            issues.append(f"{item['denko_id']}/{item['component_id']}: distance condition unresolved")
    for item in candidates_by_tab["event_access"]:
        if item["kind"] not in EVENT_ACCESS_KINDS:
            issues.append(f"{item['denko_id']}/{item['component_id']}: non-access effect leaked")
        if item["kind"] in NON_NUMERIC_ACCESS_KINDS:
            levels = json.loads(item["level_data"])
            if any(value["sort_max"] is not None or value["sort_avg"] is not None for value in levels.values()):
                issues.append(f"{item['denko_id']}/{item['component_id']}: access behavior has numeric metric")
    leaked_kinds = {
        item["kind"]
        for item in candidates_by_tab["event_access"]
        if item["kind"] in {"link_bonus", "radar_detection_range", "station_link_transfer", "today_new_station_bonus", "mile_gain"}
    }
    if leaked_kinds:
        issues.append("non-access utility kinds leaked: " + ",".join(sorted(leaked_kinds)))

    expected_lv50 = {
        ("condition_station_count", "original:028", "atk_buff_1"): (55.0, 27.5),
        ("condition_station_count", "original:067", "damage_reduction_1"): (98.0, 49.0),
        ("condition_station_count", "original:099", "exp_gain_1"): (1450.0, 725.5),
        ("condition_distance", "original:044", "atk_buff_1"): (28.0, 14.0),
        ("condition_distance", "original:044", "atk_buff_2"): (26.0, 13.0),
        ("condition_distance", "original:069", "exp_gain_1"): (150.0, 75.0),
        ("condition_distance", "original:069", "exp_gain_2"): (140.0, 140.0),
        ("event_access", "extra:001", "memory_access_station_count"): (5.0, 5.0),
    }
    for (tab_id, denko_id, component_id), expected in expected_lv50.items():
        item = next(
            (
                candidate
                for candidate in candidates_by_tab[tab_id]
                if candidate["denko_id"] == denko_id and candidate["component_id"] == component_id
            ),
            None,
        )
        levels = json.loads(item["level_data"]) if item else {}
        lv50 = levels.get("50")
        actual = (lv50.get("sort_max"), lv50.get("sort_avg")) if lv50 else None
        if actual != expected:
            issues.append(f"{denko_id}/{component_id}: Lv50 metric expected={expected} actual={actual}")
    if issues:
        raise ValueError("expedition/access audit failed: " + "; ".join(issues))


def utility_interactive_script(default_tab: str) -> str:
    script = base.interactive_script(default_tab)
    replacements = {
        "const sortKeysByColumn = ['rank', 'name', 'attr', 'type', 'effect', 'max', 'avg', 'level', 'probability', 'duration', 'cooldown', 'activation', 'target', 'condition'];":
            "const sortKeysByColumn = ['rank', 'name', 'attr', 'type', 'effect', 'max', 'avg', 'level', 'probability', 'duration', 'cooldown', 'activation', 'direction', 'weather', 'target', 'condition'];",
        "const indexMap = { name: 1, attr: 2, type: 3, effect: 4, level: 7, activation: 11, target: 12, condition: 13 };":
            "const indexMap = { name: 1, attr: 2, type: 3, effect: 4, level: 7, activation: 11, direction: 12, weather: 13, target: 14, condition: 15 };",
        "['name', 'attr', 'type', 'effect', 'level', 'activation', 'target', 'condition'].includes(key)":
            "['name', 'attr', 'type', 'effect', 'level', 'activation', 'direction', 'weather', 'target', 'condition'].includes(key)",
    }
    for old, new in replacements.items():
        if old not in script:
            raise RuntimeError(f"utility script adapter target missing: {old}")
        script = script.replace(old, new, 1)
    return script


def main() -> None:
    rows = base.read_jsonl(SKILL_PATH)
    metadata = base.denko_metadata()
    candidates_by_tab_all = {tab_id: build_candidates(tab_id, rows, metadata) for tab_id in TABS}
    audit_nullification_candidates(candidates_by_tab_all, rows)
    audit_effect_boost_candidates(candidates_by_tab_all)
    audit_calendar_candidates(candidates_by_tab_all, rows)
    audit_cooldown_probability_candidates(candidates_by_tab_all["cooldown_probability"])
    audit_weather_temperature_candidates(candidates_by_tab_all["condition_weather_temperature"])
    audit_expedition_and_access_candidates(candidates_by_tab_all)
    visible_tabs = [tab_id for tab_id in TABS if candidates_by_tab_all[tab_id]]
    default_tab = visible_tabs[0] if visible_tabs else next(iter(TABS))
    tab_buttons = "\n".join(
        f'<button class="tab-button" type="button" data-tab="{esc(tab_id)}">{esc(TABS[tab_id]["title"])} {base.tab_count_html(candidates_by_tab_all[tab_id])}</button>'
        for tab_id in visible_tabs
    )
    sections = "\n".join(render_table(tab_id, candidates_by_tab_all[tab_id]) for tab_id in visible_tabs)
    counts = {tab_id: len(candidates_by_tab_all[tab_id]) for tab_id in TABS}

    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Ekimemo Step2 技能工具索引</title>
  <style>
    body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; margin: 24px; color: #1f2328; line-height: 1.45; }}
    h1 {{ margin-bottom: 6px; }}
    h2 {{ margin-top: 24px; border-bottom: 1px solid #d8dee4; padding-bottom: 6px; }}
    .muted {{ color: #68707c; font-size: 12px; }}
    .toolbar {{ position: sticky; top: 0; z-index: 3; background: white; border-bottom: 1px solid #d8dee4; padding: 12px 0; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
    .tabs {{ display: flex; gap: 6px; flex-wrap: wrap; margin: 12px 0; }}
    button, input, select {{ padding: 7px 9px; border: 1px solid #c9d1d9; border-radius: 4px; font-size: 14px; background: white; }}
    button {{ cursor: pointer; }}
    .tab-button.active {{ background: #0969da; color: white; border-color: #0969da; }}
    .count-main {{ font-weight: 700; }}
    .vu-count {{ margin-left: 4px; color: #68707c; font-size: 12px; font-weight: 500; }}
    .tab-button.active .vu-count {{ color: rgba(255,255,255,.78); }}
    .sortable {{ cursor: pointer; user-select: none; }}
    .sortable::after {{ content: "\\2195"; margin-left: 4px; color: #8c959f; font-size: 11px; }}
    .sortable.sort-desc::after {{ content: "\\2193"; color: #0969da; }}
    .sortable.sort-asc::after {{ content: "\\2191"; color: #0969da; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin-top: 12px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 7px 8px; vertical-align: top; }}
    th {{ background: #f6f8fa; position: sticky; top: 53px; z-index: 2; }}
    td:nth-child(10), td:nth-child(11), td:nth-child(12), td:nth-child(13), td:nth-child(14) {{ white-space: nowrap; }}
    td:nth-child(16) {{ min-width: 280px; }}
    .metric {{ min-width: 108px; }}
    .tab-no-metrics .utility-hidden-metric {{ display: none; }}
    .tab-panel:not(.tab-weather) .weather-condition-column {{ display: none; }}
    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}
    a {{ color: #0969da; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <nav aria-label="报表导航" style="margin-bottom:12px"><a href="../../docs/reports/index.html" style="color:#57606a;font-size:13px;font-weight:600">← 返回报表目录</a></nav>
  <h1>Ekimemo Step2 技能工具索引</h1>
  <p>严格按机制整理：无效化/强制结束、技能/饰品/フィルム效果量强化、CD/概率操作、明确条件索引、活动/访问次数。普通 ATK/DEF/経験値/スコア 增减不会进入工具 tab。</p>
  <div class="tabs">{tab_buttons}</div>
  <div class="toolbar">
    <input id="q" placeholder="搜索ID、名字、条件、效果" size="34">
    <select id="levelMode">
      <option value="50">Lv50</option>
      <option value="30">Lv30</option>
      <option value="80">Lv80</option>
      <option value="92">Lv92(VU)</option>
      <option value="100">Lv100(VU)</option>
    </select>
    <select id="activation">
      <option value="">全部发动</option>
      <option value="always">常驻</option>
      <option value="manual">手动</option>
      <option value="non_probability">非概率触发</option>
      <option value="probability">概率/自动</option>
    </select>
    <select id="attr">
      <option value="">全部属性</option>
      <option value="cool">cool</option>
      <option value="heat">heat</option>
      <option value="eco">eco</option>
    </select>
    <select id="type">
      <option value="">全部类型</option>
      <option value="attacker">attacker</option>
      <option value="defender">defender</option>
      <option value="supporter">supporter</option>
      <option value="trickster">trickster</option>
    </select>
  </div>
  {sections}
  {utility_interactive_script(default_tab)}
</body>
</html>
"""
    html_text = "\n".join(line.rstrip() for line in html_text.splitlines()) + "\n"
    base.write_text_lf(OUT_HTML, html_text)
    print(json.dumps({"out": str(OUT_HTML.relative_to(ROOT)), "counts": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
