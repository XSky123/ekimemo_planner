from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import original_range_ingest as range_ingest
import parse as base
import review_cycle_controller as controller


BATCH_RE = re.compile(r"(?P<pool>original|extra)_(?P<start>\d{3})_(?P<end>\d{3})_skill_facts\.jsonl$")
ATTRIBUTES = ("heat", "cool", "eco", "flat")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def normalize_value_raw(component: dict[str, Any], value: dict[str, Any]) -> bool:
    raw = value.get("value_raw")
    label = component.get("condition_label")
    if not isinstance(raw, str) or not label:
        return False
    label_number = label.strip("()")
    original = raw
    if len(set(re.findall(r"[\(（](\d+)[\)）]", raw))) >= 2:
        extracted = base.extract_labeled_probability(raw, label_number)
        if extracted:
            value["value_raw"] = extracted
            return value["value_raw"] != original
    if label_number == "1" and "(2)" in raw:
        raw = raw.split("(2)")[0].strip()
    if raw.startswith(label):
        raw = raw[len(label) :].strip()
    value["value_raw"] = raw
    return value["value_raw"] != original


def inferred_probability_label(component: dict[str, Any]) -> str | None:
    label = component.get("condition_label")
    if label:
        return label
    text = " ".join(
        str(component.get(key) or "")
        for key in ("condition_raw", "effect_role", "component_id", "effect_kind")
    )
    if "(1)" in text and "(2)" not in text:
        return "(1)"
    if "(2)" in text and "(1)" not in text:
        return "(2)"
    if "primary_effect" in text or "base_effect" in text:
        return "(1)"
    return None


def inferred_probability_label_for_value(component: dict[str, Any], value: dict[str, Any]) -> str | None:
    label = inferred_probability_label(component)
    if label:
        return label
    raw_row = value.get("raw_row") or {}
    value_raw = str(value.get("value_raw") or "")
    for key, cell in raw_row.items():
        key_labels = re.findall(r"[\(\uff08](\d+)[\)\uff09]", str(key))
        if len(key_labels) != 1:
            continue
        if value_raw and value_raw in str(cell):
            return f"({key_labels[0]})"
    return None


def infer_unit(effect_kind: str, value_raw: str) -> str:
    if "～" in value_raw or "~" in value_raw or "〜" in value_raw:
        if "%" in value_raw or "％" in value_raw:
            return "percent_range"
        return "range"
    if "倍" in value_raw:
        return "multiplier"
    if "exp" in value_raw or "経験値" in value_raw:
        return "flat_exp"
    if "%" in value_raw or "％" in value_raw:
        return "percent"
    if "時間" in value_raw or "分" in value_raw:
        return "duration"
    if effect_kind in {"score_gain", "additional_score_gain"}:
        return "score"
    return "raw"


def value_from_row_fact(component: dict[str, Any], row_fact: dict[str, Any]) -> dict[str, Any] | None:
    value_raw = row_fact.get("effect")
    if not value_raw:
        return None
    effect_kind = str(component.get("effect_kind") or "")
    probability_label = inferred_probability_label(component)
    value = {
        "value_raw": value_raw,
        "value_numeric": base.parse_signed_number(value_raw),
        "unit": infer_unit(effect_kind, value_raw),
        "probability": base.probability_for_label(row_fact.get("probability") or {}, probability_label),
        "duration": row_fact.get("duration"),
        "cooldown": row_fact.get("cooldown"),
        "skill_level": row_fact.get("skill_level"),
        "source_text": row_fact.get("special_explanation"),
        "raw_row": row_fact.get("raw_row"),
    }
    value.update(base.range_value_fields(value_raw))
    return value


def labeled_effect_value(component: dict[str, Any], row_fact: dict[str, Any]) -> str | None:
    label = component.get("condition_label")
    if not label:
        return None
    label_number = str(label).strip("()")
    raw_row = row_fact.get("raw_row") or {}
    for key, cell in raw_row.items():
        key_labels = re.findall(r"[\(\uff08](\d+)[\)\uff09]", str(key))
        if len(key_labels) == 1 and key_labels[0] == label_number and cell:
            return str(cell).strip()
    effect = row_fact.get("effect")
    if isinstance(effect, str):
        segment = base.extract_labeled_condition_text(effect, f"({label_number})")
        if segment and segment != effect:
            return segment.strip()
    return None


def normalize_condition_only_value(component: dict[str, Any], value: dict[str, Any]) -> bool:
    effect_kind = component.get("effect_kind")
    raw = value.get("value_raw")
    row_fact = value.get("raw_row")
    if raw != effect_kind or not isinstance(row_fact, dict):
        return False
    source_row = {
        "effect": row_fact.get("効果") or " ".join(str(v) for k, v in row_fact.items() if "効果" in str(k) and v),
        "raw_row": row_fact,
    }
    labeled = labeled_effect_value(component, source_row)
    if not labeled:
        return False
    value["value_raw"] = labeled
    value["value_numeric"] = base.parse_signed_number(labeled)
    value["unit"] = infer_unit(str(effect_kind or ""), labeled)
    value.update(base.range_value_fields(labeled))
    return True


def normalize_fallback_component(component: dict[str, Any], row: dict[str, Any]) -> int:
    if not str(component.get("component_id") or "").startswith("component_"):
        return 0
    values = component.setdefault("values_by_denko_level", {})
    changed = 0
    for level, row_fact in (row.get("values_by_denko_level") or {}).items():
        if level in values:
            continue
        value = value_from_row_fact(component, row_fact)
        if value:
            values[level] = value
            changed += 1
    if changed:
        reasons = component.setdefault("review_reasons", [])
        component["review_reasons"] = [reason for reason in reasons if reason != "component_values_not_parsed"]
        component["confidence"] = "medium"
        component["needs_review"] = True
    return changed


def normalize_fallback_component_id(component: dict[str, Any], used_ids: set[str]) -> bool:
    component_id = str(component.get("component_id") or "")
    if not component_id.startswith("component_"):
        used_ids.add(component_id)
        return False
    effect_kind = str(component.get("effect_kind") or "")
    if not effect_kind or effect_kind in used_ids:
        used_ids.add(component_id)
        return False
    component["component_id"] = effect_kind
    used_ids.add(effect_kind)
    return True


def component_source_texts(component: dict[str, Any]) -> list[str]:
    texts = [
        str(component.get("condition_raw") or ""),
        str(component.get("remarks_raw") or ""),
    ]
    for value in (component.get("values_by_denko_level") or {}).values():
        if value.get("source_text"):
            texts.append(str(value["source_text"]))
        raw_row = value.get("raw_row") or {}
        texts.extend(str(cell) for cell in raw_row.values() if cell)
    return texts


def row_source_text(row: dict[str, Any]) -> str:
    texts = [
        str(row.get("effect_summary") or ""),
        str(row.get("trigger_condition") or ""),
        str(row.get("skill_name") or ""),
    ]
    for value in (row.get("values_by_denko_level") or {}).values():
        if value.get("special_explanation"):
            texts.append(str(value["special_explanation"]))
        raw_row = value.get("raw_row") or {}
        texts.extend(str(cell) for cell in raw_row.values() if cell)
    for component in row.get("skill_components") or []:
        texts.extend(component_source_texts(component))
    return " ".join(texts)


def row_fact_source_text(row: dict[str, Any]) -> str:
    texts = [
        str(row.get("effect_summary") or ""),
        str(row.get("trigger_condition") or ""),
        str(row.get("skill_name") or ""),
    ]
    for value in (row.get("values_by_denko_level") or {}).values():
        if value.get("special_explanation"):
            texts.append(str(value["special_explanation"]))
        raw_row = value.get("raw_row") or {}
        texts.extend(str(cell) for cell in raw_row.values() if cell)
    return " ".join(texts)


def infer_own_team_all_attribute(component: dict[str, Any]) -> str | None:
    joined = " ".join(component_source_texts(component))
    for attr in ATTRIBUTES:
        patterns = [
            rf"(?:全て|すべて){attr}属性",
            rf"属性が{attr}のみ",
            rf"編成(?:している|内|内の)?でんこが(?:全て|すべて){attr}属性",
            rf"編成内(?:の)?でんこが(?:全て|すべて){attr}属性",
            rf"編成全員が{attr}属性",
        ]
        if any(re.search(pattern, joined) for pattern in patterns):
            return attr
    return None


def fill_attribute_placeholder(text: str, attr: str) -> str:
    text = base.clean_condition_text(text) or text
    replacements = {
        "編成全員が かつ": f"編成全員が{attr}属性かつ",
        "編成全員が　かつ": f"編成全員が{attr}属性かつ",
        "編成内が全て のとき": f"編成内が全て{attr}属性のとき",
        "編成内が全て　のとき": f"編成内が全て{attr}属性のとき",
        "編成しているでんこがすべて で": f"編成しているでんこがすべて{attr}属性で",
        "編成しているでんこがすべて　で": f"編成しているでんこがすべて{attr}属性で",
        "発動条件： のみの編成": f"発動条件：{attr}属性のみの編成",
        "発動条件：　のみの編成": f"発動条件：{attr}属性のみの編成",
        "全て かつ": f"全て{attr}属性かつ",
        "全て　かつ": f"全て{attr}属性かつ",
        "全て のとき": f"全て{attr}属性のとき",
        "全て　のとき": f"全て{attr}属性のとき",
        "全て の時": f"全て{attr}属性の時",
        "全て　の時": f"全て{attr}属性の時",
        "全て の場合": f"全て{attr}属性の場合",
        "全て　の場合": f"全て{attr}属性の場合",
        "すべて かつ": f"すべて{attr}属性かつ",
        "すべて　かつ": f"すべて{attr}属性かつ",
        "すべて で": f"すべて{attr}属性で",
        "すべて　で": f"すべて{attr}属性で",
        "すべて の時": f"すべて{attr}属性の時",
        "すべて　の時": f"すべて{attr}属性の時",
        "すべて の場合": f"すべて{attr}属性の場合",
        "すべて　の場合": f"すべて{attr}属性の場合",
    }
    for before, after in replacements.items():
        text = text.replace(before, after)
    text = re.sub(rf"({attr}属性のみの編成)[\s　]+{attr}属性", r"\1", text)
    text = re.sub(rf"[\s　]+{attr}属性$", "", text)
    return text


def condition_has_opponent_access_attribute(condition: str, attr: str) -> bool:
    return bool(
        re.search(rf"{attr}属性.*?からアクセスされ", condition)
        or re.search(rf"からアクセスされ.*?{attr}属性", condition)
    )


def infer_component_attribute(component: dict[str, Any]) -> str | None:
    filters = component.get("target_filters") or {}
    candidates = [
        filters.get("attribute"),
        filters.get("own_team_all_attribute"),
        (filters.get("opponent_team_attribute_count") or {}).get("attribute"),
        (filters.get("opponent_team_attribute_min_count") or {}).get("attribute"),
    ]
    disabled_skill_target = str(filters.get("disabled_skill_target") or "")
    disabled_match = re.search(r"(heat|cool|eco)属性", disabled_skill_target)
    if disabled_match:
        candidates.append(disabled_match.group(1))
    for candidate in candidates:
        if candidate in ATTRIBUTES:
            return str(candidate)
    condition = str(component.get("condition_raw") or "")
    match = re.search(r"(heat|cool|eco)(?:属性)?(?:の)?でんこ", condition)
    return match.group(1) if match else None


def normalize_count_attribute_placeholder(component: dict[str, Any]) -> bool:
    condition = component.get("condition_raw")
    if not isinstance(condition, str):
        return False
    attr = infer_component_attribute(component)
    if attr not in ATTRIBUTES:
        return False
    normalized = condition
    normalized = re.sub(
        r"相手と自身の編成内の[\s　]+の数",
        f"相手と自身の編成内の{attr}属性でんこの数",
        normalized,
    )
    normalized = re.sub(
        r"編成内の[\s　]+の数",
        f"編成内の{attr}属性でんこの数",
        normalized,
    )
    normalized = re.sub(
        r"スキル無効化\([\s　]*\)",
        f"スキル無効化({attr}属性でんこ)",
        normalized,
    )
    normalized = re.sub(
        r"編成内の[\s　]+の(ATK|DEF)",
        rf"編成内の{attr}属性でんこの\1",
        normalized,
    )
    normalized = re.sub(
        r"編成内[\s　]+の(ATK|DEF)",
        rf"編成内{attr}属性でんこの\1",
        normalized,
    )
    normalized = re.sub(
        r"編成内のでんこがすべて[\s　]+のとき",
        f"編成内のでんこがすべて{attr}属性のとき",
        normalized,
    )
    normalized = re.sub(
        r"自編成のでんこが全員[\s　]+のとき",
        f"自編成のでんこが全員{attr}属性のとき",
        normalized,
    )
    normalized = re.sub(
        r"([（(]\d[）)]\s*)[\s　]+のアクセス時",
        rf"\1{attr}属性でんこのアクセス時",
        normalized,
    )
    normalized = re.sub(rf"(?<=変動)[\s　]+{attr}(?:属性)?(?:の)?でんこ", "", normalized)
    normalized = re.sub(
        rf"(?<=\))[\s　]+{attr}(?:属性)?(?:の)?でんこ(?=(?:\s*アクセス時|\s*アクセスされた|\s*$))",
        "",
        normalized,
    )
    normalized = re.sub(
        r"(?<=heat＆cool属性のDEF増加)[\s　]+(?:heat|cool|eco)(?:属性)?(?:の)?でんこ",
        "",
        normalized,
    )
    normalized = re.sub(rf"[\s　]+{attr}(?:属性)?(?:の)?でんこ(?=(?:\s*/|\s*[（(]\d|\s*天気は|\s*$))", "", normalized)
    if normalized != condition:
        component["condition_raw"] = base.clean_condition_text(normalized) or normalized
        return True
    return False


def normalize_opponent_access_attribute_phrase(component: dict[str, Any]) -> bool:
    condition = component.get("condition_raw")
    if not isinstance(condition, str):
        return False
    filters = component.get("target_filters") or {}
    attr = filters.get("opponent_attribute")
    if attr not in ATTRIBUTES:
        return False
    normalized = re.sub(
        rf"([（(]\d[）)]\s*)からアクセスされる",
        rf"\1{attr}属性のでんこからアクセスされる",
        condition,
    )
    normalized = re.sub(rf"(?<=\))[\s　]*{attr}属性$", "", normalized)
    normalized = re.sub(rf"[\s　]+{attr}属性$", "", normalized)
    if normalized != condition:
        component["condition_raw"] = base.clean_condition_text(normalized) or normalized
        return True
    return False


def normalize_attribute_placeholders(row: dict[str, Any], component: dict[str, Any]) -> bool:
    attr = infer_own_team_all_attribute(component)
    changed = False
    if attr:
        filters = component.setdefault("target_filters", {})
        if filters.get("own_team_all_attribute") != attr:
            filters["own_team_all_attribute"] = attr
            changed = True
    for key in ("condition_raw", "remarks_raw"):
        value = component.get(key)
        if isinstance(value, str) and attr:
            normalized = fill_attribute_placeholder(value, attr)
            if normalized != value:
                component[key] = normalized
                changed = True
    for key in ("effect_summary", "trigger_condition"):
        value = row.get(key)
        if isinstance(value, str) and attr:
            normalized = fill_attribute_placeholder(value, attr)
            if normalized != value:
                row[key] = normalized
                changed = True
    return changed


def normalize_access_direction(component: dict[str, Any]) -> bool:
    text = " ".join(component_source_texts(component))
    condition = str(component.get("condition_raw") or "")
    trigger = component.setdefault("trigger_conditions", {})
    original = json.dumps(trigger, ensure_ascii=False, sort_keys=True)
    direction_basis = condition or text
    passive = any(phrase in direction_basis for phrase in ["アクセスされた", "アクセスされる", "アクセスされて", "被アクセス", "フットバーされ"])
    active_text = direction_basis
    for noise in ["アクセス時にカウンターを受けた", "カウンターを受けたとき", "カウンターを受けた時"]:
        active_text = active_text.replace(noise, "")
    active = bool(
        re.search(r"(?<!被)アクセス時", active_text)
        or any(phrase in active_text for phrase in ["アクセスしたとき", "アクセスした時", "アクセスする", "チェックイン時"])
    )
    if any(phrase in condition for phrase in ["アクセスした・された", "アクセス時・被アクセス時", "アクセス時/被アクセス時"]):
        active = True
        passive = True
    if "被アクセス" in condition and not bool(re.search(r"(?<!被)アクセス時|アクセスした|チェックイン時", condition)):
        active = False
    if passive and active:
        trigger["access_directions"] = ["active", "passive"]
        trigger["event_hint"] = "access"
        trigger.pop("access_direction", None)
    elif passive:
        trigger["access_direction"] = "passive"
        trigger["event_hint"] = "accessed"
        trigger.pop("access_directions", None)
    elif active and trigger.get("access_direction") not in {"passive"}:
        trigger["access_direction"] = "active"
        trigger.setdefault("event_hint", "access")
        trigger.pop("access_directions", None)
    return json.dumps(trigger, ensure_ascii=False, sort_keys=True) != original


def normalize_scope_and_filters(component: dict[str, Any]) -> bool:
    text = " ".join(component_source_texts(component))
    condition = component.get("condition_raw") or ""
    filters = component.setdefault("target_filters", {})
    before = json.dumps(
        {
            "target_scope": component.get("target_scope"),
            "target_filters": filters,
            "trigger_conditions": component.get("trigger_conditions"),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    own_attr = filters.get("own_team_all_attribute")
    if (
        own_attr
        and filters.get("opponent_attribute") == own_attr
        and not re.search(rf"相手(?:が|のでんこが|編成内.*?){own_attr}属性", text)
    ):
        filters.pop("opponent_attribute", None)
    for attr in ATTRIBUTES:
        combined_count = bool(
            re.search(rf"相手と自身の編成内の{attr}属性(?:の)?でんこの数", text)
            or re.search(rf"相手と自身の編成内の\s*の数.*?{attr}属性(?:の)?でんこ", condition)
        )
        if combined_count:
            filters.pop("attribute", None)
            count_filter = filters.setdefault("opponent_team_attribute_count", {})
            count_filter["attribute"] = attr
            count_filter["includes_own_team"] = True
            component.setdefault("scaling_conditions", {})["count_basis"] = "own_and_opponent_team"
            component["scaling_conditions"]["count_attribute"] = attr
            cap_match = re.search(r"上限\s*(\d+)\s*体", condition)
            if cap_match:
                count_filter["max_count"] = int(cap_match.group(1))
        if re.search(rf"相手(?:の)?編成(?:内|の)?(?:の)?{attr}属性(?:の)?(?:でんこ)?(?:の)?数", condition) or re.search(
            rf"相手(?:の)?編成(?:内|の)?(?:の)?{attr}属性(?:の)?数", text
        ):
            filters.pop("attribute", None)
            filters["opponent_team_attribute_count"] = {"attribute": attr}
            cap_match = re.search(r"上限\s*(\d+)\s*体", condition)
            if cap_match:
                filters["opponent_team_attribute_count"]["max_count"] = int(cap_match.group(1))
        if re.search(rf"{attr}属性.*?からアクセスされ", condition):
            filters.pop("attribute", None)
            filters["opponent_attribute"] = attr
        if condition_has_opponent_access_attribute(condition, attr):
            filters.pop("attribute", None)
            filters["opponent_attribute"] = attr
        if re.search(rf"相手が{attr}属性", condition):
            filters["opponent_attribute"] = attr
    if "自身の編成の先頭車両のでんこ" in text and "相手の先頭車両のでんこ" in text:
        component["target_scope"] = ["own_front_car", "opponent_front_car"]
    elif re.search(r"編成内の(?:heat属性とcool属性|heat＆cool属性|cool属性とeco属性|heat属性とeco属性).*?DEF", text):
        component["target_scope"] = ["team_all"]
    elif "編成内" in text and "HPを回復" in text and component.get("effect_kind") == "hp_recovery":
        component["target_scope"] = ["team_all"]
    elif "編成内のでんこのATK" in text or "編成内のでんこのDEF" in text:
        component["target_scope"] = ["team_all"]
    if "2駅以上リンクしている" in condition:
        component.setdefault("trigger_conditions", {})["linked_station_min_count"] = 2
    elif component.get("trigger_conditions", {}).get("linked_station_min_count") == 2:
        component["trigger_conditions"].pop("linked_station_min_count", None)
    label = component.get("condition_label")
    if "2駅以上リンクしている がいる" in condition and label:
        attrs = re.findall(r"2駅以上リンクしている(heat|cool|eco|flat)属性のでんこがいる", text)
        label_index = int(str(label).strip("()")) - 1
        if 0 <= label_index < len(attrs):
            component["condition_raw"] = condition.replace("2駅以上リンクしている がいる", f"2駅以上リンクしている{attrs[label_index]}属性のでんこがいる")
            component.setdefault("trigger_conditions", {})["linked_denko_attribute"] = attrs[label_index]
    own_attr = filters.get("own_team_all_attribute")
    if own_attr:
        trigger = component.get("trigger_conditions") or {}
        for key, value in list(trigger.items()):
            if isinstance(value, str):
                trigger[key] = fill_attribute_placeholder(value, own_attr)
    return (
        json.dumps(
            {
                "target_scope": component.get("target_scope"),
                "target_filters": filters,
                "trigger_conditions": component.get("trigger_conditions"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        != before
    )


def next_component_id(base_id: str, components: list[dict[str, Any]]) -> str:
    used = {str(component.get("component_id") or "") for component in components}
    if base_id not in used:
        return base_id
    index = 2
    while f"{base_id}_{index}" in used:
        index += 1
    return f"{base_id}_{index}"


def clone_values_for_effect(component: dict[str, Any], effect_kind: str, value_raw: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for level, source in (component.get("values_by_denko_level") or {}).items():
        copied = dict(source)
        copied["value_raw"] = value_raw
        copied["value_numeric"] = base.parse_signed_number(value_raw)
        copied["unit"] = infer_unit(effect_kind, value_raw)
        copied.update(base.range_value_fields(value_raw))
        values[level] = copied
    return values


def add_supplemental_component(
    row: dict[str, Any],
    *,
    effect_kind: str,
    condition_raw: str,
    source_component: dict[str, Any] | None = None,
    value_raw: str | None = None,
    component_id: str | None = None,
    target_scope: list[str] | None = None,
    target_filters: dict[str, Any] | None = None,
    trigger_conditions: dict[str, Any] | None = None,
    condition_label: str | None = None,
) -> bool:
    components = row.setdefault("skill_components", [])
    if any(component.get("effect_kind") == effect_kind and component.get("condition_raw") == condition_raw for component in components):
        return False
    if source_component is None and components:
        source_component = components[0]
    values: dict[str, Any] = {}
    if source_component is not None:
        values = clone_values_for_effect(source_component, effect_kind, value_raw or effect_kind)
    else:
        for level, row_fact in (row.get("values_by_denko_level") or {}).items():
            values[level] = fallback_value_from_row(row, {"effect_kind": effect_kind}, level, row_fact) or {}
            values[level]["value_raw"] = value_raw or values[level].get("value_raw") or effect_kind
    component = {
        "activation_type": row.get("activation_type") or (source_component or {}).get("activation_type"),
        "availability": (source_component or {}).get("availability")
        or {
            "levels": sorted((row.get("values_by_denko_level") or {}).keys(), key=lambda value: int(value)),
            "vu_only": False,
        },
        "component_id": next_component_id(component_id or effect_kind, components),
        "condition_label": condition_label or (source_component or {}).get("condition_label"),
        "condition_raw": condition_raw,
        "confidence": "medium",
        "effect_kind": effect_kind,
        "effect_role": "supplemental_effect",
        "needs_review": True,
        "remarks_raw": (source_component or {}).get("remarks_raw"),
        "review_reasons": ["supplemental_component_from_source_text"],
        "scaling_conditions": base.infer_scaling_conditions(condition_raw),
        "target_filters": dict(target_filters if target_filters is not None else (source_component or {}).get("target_filters") or {}),
        "target_scope": list(target_scope if target_scope is not None else (source_component or {}).get("target_scope") or []),
        "trigger_conditions": dict(trigger_conditions if trigger_conditions is not None else (source_component or {}).get("trigger_conditions") or {}),
        "values_by_denko_level": values,
    }
    components.append(component)
    return True


def newest_component(row: dict[str, Any], effect_kind: str, condition_raw: str) -> dict[str, Any] | None:
    for component in reversed(row.get("skill_components") or []):
        if component.get("effect_kind") == effect_kind and component.get("condition_raw") == condition_raw:
            return component
    return None


def use_raw_row_value_field(component: dict[str, Any], field_name: str, *, unit: str | None = None) -> None:
    for value in (component.get("values_by_denko_level") or {}).values():
        raw_row = value.get("raw_row") or {}
        raw_value = raw_row.get(field_name)
        if not raw_value:
            continue
        value["value_raw"] = str(raw_value)
        value["value_numeric"] = base.parse_signed_number(str(raw_value))
        if unit:
            value["unit"] = unit


def normalize_supplemental_components(row: dict[str, Any]) -> int:
    changed = 0
    text = row_source_text(row)
    components = row.get("skill_components") or []
    kinds = {component.get("effect_kind") for component in components}
    fact_text = row_fact_source_text(row)
    positive_counter = bool(re.search(r"カウンター(?:する|します|されそう|$|、)", fact_text))
    if "カウンター" in fact_text and "counter" not in kinds and positive_counter:
        source = next((component for component in components if "カウンター" in " ".join(component_source_texts(component))), None)
        if add_supplemental_component(
            row,
            effect_kind="counter",
            condition_raw=base.clean_condition_text("カウンター") or "カウンター",
            source_component=source,
            value_raw="カウンター",
            target_scope=["self"],
            trigger_conditions={"access_direction": "passive", "event_hint": "accessed"},
        ):
            changed += 1
    if ("ATKとDEFが増加" in text or "ATK・DEF" in text or "ATK&DEF" in text) and "atk_buff" not in kinds:
        source = next((component for component in components if component.get("effect_kind") in {"exp_gain", "score_gain"}), None)
        if add_supplemental_component(row, effect_kind="atk_buff", condition_raw="自身のATK増加", source_component=source, value_raw="ATK増加", target_scope=["self"]):
            changed += 1
    if ("ATKとDEFが増加" in text or "ATK・DEF" in text or "ATK&DEF" in text) and "def_buff" not in kinds:
        source = next((component for component in components if component.get("effect_kind") in {"atk_buff", "exp_gain", "score_gain"}), None)
        if add_supplemental_component(row, effect_kind="def_buff", condition_raw="自身のDEF増加", source_component=source, value_raw="DEF増加", target_scope=["self"]):
            changed += 1
    positive_link_bonus = (
        "リンクボーナス増加" in text
        or "リンクするときに獲得するボーナスが増加" in text
        or "リンクするときに獲得するボーナス（アクセスしたでんこ）" in text
    )
    negative_link_bonus = (
        "リンクボーナスが0" in text
        or "リンクボーナスのスコアが0" in text
        or "リンクするときに獲得するボーナスが0" in text
        or "リンクボーナスを増加するスキルは効果の対象外" in text
    )
    zero_link_bonus = (
        "リンクボーナスが0" in text
        or "リンクボーナスのスコアが0" in text
        or "リンクするときに獲得するボーナスが0" in text
    )
    if positive_link_bonus and not negative_link_bonus and "link_bonus" not in kinds:
        source = next((component for component in components if component.get("condition_label") == "(2)"), None) or (components[0] if components else None)
        if add_supplemental_component(row, effect_kind="link_bonus", condition_raw="リンクボーナス増加", source_component=source, value_raw="リンクボーナス増加", target_scope=["team_all"]):
            changed += 1
    if zero_link_bonus and "link_bonus_zero" not in kinds:
        source = next((component for component in components if component.get("condition_label") == "(2)"), None) or (components[0] if components else None)
        condition = "(2)相手にダメージを与えてリンクしたとき、リンクボーナスのスコアが0になる"
        if add_supplemental_component(
            row,
            effect_kind="link_bonus_zero",
            condition_raw=condition,
            source_component=source,
            value_raw="リンクボーナス0",
            target_scope=["team_all"],
            trigger_conditions={"access_direction": "active", "event_hint": "link"},
            condition_label="(2)",
        ):
            changed += 1
            kinds.add("link_bonus_zero")
            components = row.get("skill_components") or []
    if "クールタイムを短縮することがあります" in text and "クールタイム-5%" in text and "cooldown_reduction" not in kinds:
        source = next((component for component in components if component.get("condition_label") == "(2)"), None) or (components[0] if components else None)
        condition = "(2)クールダウン状態の編成内でんこがリンク時、そのでんこのクールタイム-5%"
        if add_supplemental_component(
            row,
            effect_kind="cooldown_reduction",
            condition_raw=condition,
            source_component=source,
            value_raw="クールタイム-5%",
            target_scope=["team_all"],
            target_filters={"state": "cooldown"},
            trigger_conditions={"event_hint": "link"},
            condition_label="(2)",
        ):
            changed += 1
            kinds.add("cooldown_reduction")
            components = row.get("skill_components") or []
    has_cooldown_entry_count = any(
        "(2)回数" in (value.get("raw_row") or {}) for component in components for value in (component.get("values_by_denko_level") or {}).values()
    )
    if "クールタイムに入ります" in text and has_cooldown_entry_count and "cooldown_entry" not in kinds:
        source = next((component for component in components if component.get("condition_label") == "(2)"), None) or (components[0] if components else None)
        condition = "(2)編成内でんこが一定回数リンク成功でクールタイム入り"
        if add_supplemental_component(
            row,
            effect_kind="cooldown_entry",
            condition_raw=condition,
            source_component=source,
            value_raw="リンク回数でクールタイム入り",
            target_scope=["team_all"],
            target_filters=dict((source or {}).get("target_filters") or {}),
            trigger_conditions={"event_hint": "link"},
            condition_label="(2)",
        ):
            component = newest_component(row, "cooldown_entry", condition)
            if component:
                use_raw_row_value_field(component, "(2)回数", unit="count")
            changed += 1
            kinds.add("cooldown_entry")
            components = row.get("skill_components") or []
    if ("経験値" in text and "スコア" in text) and "exp_gain" not in kinds:
        source = next((component for component in components if component.get("effect_kind") == "score_gain"), None)
        if add_supplemental_component(row, effect_kind="exp_gain", condition_raw=(source or {}).get("condition_raw") or "経験値付与", source_component=source, value_raw="経験値付与"):
            changed += 1
    if ("経験値" in text and "スコア" in text) and not ({"score_gain", "score_random_modifier"} & kinds):
        source = next((component for component in components if component.get("effect_kind") == "exp_gain"), None)
        if add_supplemental_component(row, effect_kind="score_gain", condition_raw=(source or {}).get("condition_raw") or "スコア獲得", source_component=source, value_raw="スコア獲得"):
            changed += 1
    if "フットバース無効化" in text and "skill_disable" not in kinds:
        source = next((component for component in components if component.get("effect_kind") == "reboot"), None)
        if add_supplemental_component(row, effect_kind="skill_disable", condition_raw="フットバース無効化", source_component=source, value_raw="フットバース無効化", target_scope=["opponent_denko"]):
            changed += 1
    for attr in ATTRIBUTES:
        if f"相手が{attr}属性" in text and f"相手が{attr}属性時" in text and not any(
            (component.get("target_filters") or {}).get("opponent_attribute") == attr for component in row.get("skill_components") or []
        ):
            source = next((component for component in row.get("skill_components") or [] if component.get("effect_kind") in {"score_gain", "exp_gain"}), None)
            if add_supplemental_component(
                row,
                effect_kind="effect_multiplier",
                condition_raw=f"相手が{attr}属性時に効果量増加",
                source_component=source,
                value_raw="効果量増加",
                target_scope=["team_all"],
                target_filters={"opponent_attribute": attr},
            ):
                changed += 1
    return changed


def cleanup_overbroad_supplements(row: dict[str, Any]) -> int:
    changed = 0
    text = row_source_text(row)
    fact_text = row_fact_source_text(row)
    components = row.get("skill_components") or []
    cleaned: list[dict[str, Any]] = []
    for component in components:
        reasons = component.get("review_reasons") or []
        effect_kind = component.get("effect_kind")
        condition = str(component.get("condition_raw") or "")
        if "supplemental_component_from_source_text" in reasons:
            if effect_kind == "cooldown_reduction" and "クールタイム-5%" not in fact_text:
                changed += 1
                continue
            if effect_kind == "link_bonus_zero" and not (
                "リンクボーナスが0" in fact_text
                or "リンクボーナスのスコアが0" in fact_text
                or "リンクするときに獲得するボーナスが0" in fact_text
            ):
                changed += 1
                continue
            if effect_kind == "link_bonus" and (
                "リンクボーナスが0" in text
                or "リンクボーナスのスコアが0" in text
                or "リンクするときに獲得するボーナスが0" in text
                or "リンクボーナスを増加するスキルは効果の対象外" in text
                or ("リンクボーナス増加" not in text and "リンクするときに獲得するボーナスが増加" not in text)
            ):
                changed += 1
                continue
            if effect_kind == "counter" and not re.search(r"カウンター(?:する|します|されそう|$|、)", row_fact_source_text(row)):
                changed += 1
                continue
        filters = component.setdefault("target_filters", {})
        before_filters = dict(filters)
        for attr in ATTRIBUTES:
            if (
                filters.get("opponent_attribute") == attr
                and f"相手が{attr}属性" not in condition
                and not condition_has_opponent_access_attribute(condition, attr)
            ):
                filters.pop("opponent_attribute", None)
        if filters != before_filters:
            changed += 1
        trigger = component.setdefault("trigger_conditions", {})
        before_trigger = dict(trigger)
        if trigger.get("access_direction") in {"active", "passive"} and trigger.get("access_directions"):
            trigger.pop("access_directions", None)
        if trigger.get("access_directions") == ["active", "passive"] and "被アクセス" in condition and not bool(
            re.search(r"(?<!被)アクセス時|アクセスした|チェックイン時", condition)
        ):
            trigger.pop("access_directions", None)
            trigger["access_direction"] = "passive"
            trigger["event_hint"] = "accessed"
        if trigger != before_trigger:
            changed += 1
        cleaned.append(component)
    if len(cleaned) != len(components):
        row["skill_components"] = cleaned
    return changed


def fallback_effect_kind(row: dict[str, Any]) -> str | None:
    text = " ".join(
        str(value or "")
        for value in [
            row.get("effect_summary"),
            row.get("trigger_condition"),
            row.get("skill_name"),
            ((row.get("values_by_denko_level") or {}).get("50") or {}).get("effect"),
        ]
    )
    if row.get("skill_name") == "スキルはありません":
        return "none"
    if "スキル発動率" in text:
        return "activation_probability_boost"
    if "クールタイム解除" in text:
        return "cooldown_reset"
    if "譲渡" in text or "受け渡す駅" in text:
        return "station_link_transfer"
    if "肩代わり" in text:
        return "damage_substitution"
    if "ダメージを0" in text or "ダメージ無効化" in text:
        return "damage_nullification"
    if "AP減少" in text or "AP -" in text:
        return "ap_debuff"
    if "フィルム" in text and ("2倍" in text or "効果" in text):
        return "film_effect_multiplier"
    if "最多アクセス駅" in text and "アクセス" in text:
        return "remote_station_access"
    if "効果時間延長" in text or "効果時間" in text and "延長" in text:
        return "duration_extension"
    if "今日の新駅" in text and "ボーナス" in text:
        return "today_new_station_bonus"
    if "リンクボーナス" in text:
        return "link_bonus"
    if "カウンター" in text:
        return "counter"
    if "リンク継続" in text or "リンクを継続" in text or "リンクを手放さず" in text:
        return "link_retention"
    return None


def fallback_value_from_row(row: dict[str, Any], component: dict[str, Any], level: str, row_fact: dict[str, Any]) -> dict[str, Any] | None:
    value = value_from_row_fact(component, row_fact)
    if value:
        return value
    raw = row_fact.get("effect") or row.get("effect_summary") or row.get("trigger_condition") or component.get("effect_kind")
    if not raw and component.get("effect_kind") != "none":
        return None
    raw = raw or "スキルなし"
    value = {
        "value_raw": raw,
        "value_numeric": base.parse_signed_number(raw),
        "unit": infer_unit(str(component.get("effect_kind") or ""), raw),
        "probability": row_fact.get("probability") or {},
        "duration": row_fact.get("duration"),
        "cooldown": row_fact.get("cooldown"),
        "skill_level": row_fact.get("skill_level") or f"でんこLv.{level}",
        "source_text": row_fact.get("special_explanation"),
        "raw_row": row_fact.get("raw_row"),
    }
    value.update(base.range_value_fields(raw))
    return value


def create_fallback_component(row: dict[str, Any]) -> bool:
    if row.get("skill_components"):
        return False
    effect_kind = fallback_effect_kind(row)
    if not effect_kind:
        return False
    condition = row.get("trigger_condition") or row.get("effect_summary") or ""
    component = {
        "activation_type": row.get("activation_type"),
        "availability": {
            "levels": sorted((row.get("values_by_denko_level") or {}).keys(), key=lambda value: int(value)),
            "vu_only": False,
        },
        "component_id": effect_kind,
        "condition_label": None,
        "condition_raw": condition,
        "confidence": "medium",
        "effect_kind": effect_kind,
        "effect_role": None,
        "needs_review": True,
        "remarks_raw": None,
        "review_reasons": ["fallback_component_from_level_table"],
        "scaling_conditions": base.infer_scaling_conditions(condition),
        "target_filters": base.infer_target_filters(condition, effect_kind),
        "target_scope": base.infer_target_scope(condition, effect_kind),
        "trigger_conditions": {},
        "values_by_denko_level": {},
    }
    for level, row_fact in (row.get("values_by_denko_level") or {}).items():
        value = fallback_value_from_row(row, component, level, row_fact)
        if value:
            component["values_by_denko_level"][level] = value
    if "編成内" in condition and not component["target_scope"]:
        component["target_scope"] = ["team_all"]
    if "HPが0" in condition:
        component["trigger_conditions"]["hp_zero"] = True
    if "2駅以上リンク" in condition:
        component["trigger_conditions"]["linked_station_min_count"] = 2
    row["skill_components"] = [component]
    return True


def refresh_component_review_reasons(row: dict[str, Any]) -> int:
    components = row.get("skill_components") or []
    condition_text = " ".join(str(component.get("condition_raw") or "") for component in components)
    expected_labels = {label.strip("()") for label, _segment in base.labeled_condition_segments(condition_text)}
    emitted_labels = {
        str(component.get("condition_label")).strip("()")
        for component in components
        if component.get("condition_label")
    }
    duplicate_ids = base.component_duplicate_signatures(components)
    changed = 0
    for component in components:
        before = list(component.get("review_reasons") or [])
        after = list(before)
        component_id = component.get("component_id") or ""
        if expected_labels and expected_labels.issubset(emitted_labels):
            after = [reason for reason in after if reason != "labeled_component_count_mismatch"]
        if component_id not in duplicate_ids:
            after = [reason for reason in after if reason != "duplicate_labeled_component_values_need_review"]
        if not base.has_condition_effect_mismatch(component):
            after = [reason for reason in after if reason != "condition_effect_mismatch_needs_review"]
        if not (
            base.label_declared_vu_only(component, condition_text)
            and not base.component_has_only_vu_values(component)
        ):
            after = [reason for reason in after if reason != "vu_label_level_mismatch_needs_review"]
        if after != before:
            component["review_reasons"] = after
            changed += 1
    return changed


def normalize_skill_rows(rows: list[dict[str, Any]]) -> int:
    changed = 0
    for row in rows:
        if create_fallback_component(row):
            changed += 1
        changed += normalize_supplemental_components(row)
        changed += cleanup_overbroad_supplements(row)
        used_ids: set[str] = set()
        for component in row.get("skill_components") or []:
            changed += normalize_fallback_component(component, row)
            if normalize_fallback_component_id(component, used_ids):
                changed += 1
            if normalize_attribute_placeholders(row, component):
                changed += 1
            if normalize_count_attribute_placeholder(component):
                changed += 1
            if normalize_access_direction(component):
                changed += 1
            if normalize_scope_and_filters(component):
                changed += 1
            if normalize_opponent_access_attribute_phrase(component):
                changed += 1
            for value in (component.get("values_by_denko_level") or {}).values():
                before = json.dumps(value, ensure_ascii=False, sort_keys=True)
                raw_probability = (value.get("raw_row") or {}).get("発動率")
                probability = value.get("probability")
                label = inferred_probability_label_for_value(component, value)
                if isinstance(raw_probability, str) and label and label in raw_probability:
                    probability = {"発動率": raw_probability}
                    value["probability"] = probability
                if isinstance(probability, dict) and label:
                    value["probability"] = base.probability_for_label(probability, label)
                normalize_condition_only_value(component, value)
                normalize_value_raw(component, value)
                after = json.dumps(value, ensure_ascii=False, sort_keys=True)
                if before != after:
                    changed += 1
        changed += cleanup_overbroad_supplements(row)
        row["summary_zh"] = base.build_summary_zh(
            row.get("skill_components"),
            row.get("normalized_skill"),
            (row.get("values_by_denko_level") or {}).get("50"),
            row.get("values_by_denko_level"),
        )
        changed += refresh_component_review_reasons(row)
    return changed


def rebuild_outputs(pool: str, start: int, end: int, batch_size: int) -> dict[str, str]:
    stem = range_ingest.output_stem(start, end, pool)
    denko_rows = read_jsonl(base.RECORD_DIR / f"{stem}_denko_facts.jsonl")
    skill_rows = read_jsonl(base.RECORD_DIR / f"{stem}_skill_facts.jsonl")
    reviews = read_jsonl(base.REVIEW_DIR / f"{stem}_review_queue.jsonl")
    report = range_ingest.write_html_report(start, end, denko_rows, skill_rows, reviews, batch_size, pool)
    state = controller.build_state(start, end, batch_size, run_result=None, pool=pool)
    state["paths"]["report"] = str(report.relative_to(base.ROOT))
    state_path = controller.AGENT_RUN_DIR / f"{stem}_cycle_state.json"
    controller.write_json(state_path, state)
    prompt = controller.write_batch_review_prompt(stem, state)
    return {
        "report": str(report.relative_to(base.ROOT)),
        "state": str(state_path.relative_to(base.ROOT)),
        "agent_prompt": str(prompt.relative_to(base.ROOT)),
    }


def normalize_file(path: Path, batch_size: int, rebuild: bool) -> dict[str, Any]:
    match = BATCH_RE.fullmatch(path.name)
    if not match:
        raise ValueError(f"unsupported skill facts filename: {path.name}")
    pool = match.group("pool")
    start = int(match.group("start"))
    end = int(match.group("end"))
    rows = read_jsonl(path)
    changed = normalize_skill_rows(rows)
    write_jsonl(path, rows)
    outputs = rebuild_outputs(pool, start, end, batch_size) if rebuild else {}
    return {
        "path": str(path.relative_to(base.ROOT)),
        "pool": pool,
        "start": start,
        "end": end,
        "records": len(rows),
        "changed_values": changed,
        **outputs,
    }


def selected_paths(pool: str | None, pattern: str | None) -> list[Path]:
    if pattern:
        return sorted(base.RECORD_DIR.glob(pattern))
    prefix = f"{pool}_" if pool else ""
    return sorted(base.RECORD_DIR.glob(f"{prefix}*_skill_facts.jsonl"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", choices=sorted(base.LIST_PAGES))
    parser.add_argument("--pattern", help="Optional glob under data/records, e.g. extra_*_skill_facts.jsonl")
    parser.add_argument("--batch-size", type=int, default=30)
    parser.add_argument("--no-rebuild", action="store_true")
    args = parser.parse_args()
    results = [
        normalize_file(path, args.batch_size, rebuild=not args.no_rebuild)
        for path in selected_paths(args.pool, args.pattern)
    ]
    print(json.dumps({"normalized_files": len(results), "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
