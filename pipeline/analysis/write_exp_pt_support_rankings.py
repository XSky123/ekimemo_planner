from __future__ import annotations

import html
import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline.analysis import write_attack_support_rankings as base

SKILL_PATH = ROOT / "data" / "step1_db" / "skill_facts.jsonl"
OUT_HTML = ROOT / "data" / "reports" / "step2_exp_pt_support_rankings_zh.html"
RAW_DIR = ROOT / "data" / "raw_pages"


TABS = {
    "fixed_exp": {
        "title": "固定経験値",
        "description": "有明确经验值数值的経験値付与/增加类。排序按经验值本身，不和百分比/条件型混排。",
        "metric_types": {"fixed_exp"},
        "max_header": "理论最大",
        "avg_header": "平均值",
    },
    "exp_distribution": {
        "title": "経験値分配/倍率",
        "description": "经验分配、经验比例、与伤害等条件联动的经验收益。排序按百分比/倍率，不和固定经验混排。",
        "metric_types": {"exp_ratio"},
        "max_header": "比例/倍率最大",
        "avg_header": "比例/倍率平均",
    },
    "fixed_score": {
        "title": "固定スコア",
        "description": "有明确数值的スコア/PT獲得。排序按 pt 数值，不和百分比/倍率混排。",
        "metric_types": {"fixed_score"},
        "max_header": "理论最大",
        "avg_header": "平均值",
    },
    "score_modifier": {
        "title": "スコア倍率/変動",
        "description": "访问スコア增加、随机スコア增减、受伤害比例换算等百分比/倍率型收益。排序按百分比或倍率。",
        "metric_types": {"score_percent_modifier"},
        "max_header": "倍率/比例最大",
        "avg_header": "倍率/比例平均",
    },
    "bonus_gain": {
        "title": "ボーナス/マイル",
        "description": "リンクボーナス、今日の新駅ボーナス、マイル付与等偏 PT/通勤收益的技能。",
        "metric_types": {"bonus_gain"},
        "max_header": "理论最大",
        "avg_header": "平均值",
    },
    "condition_unknown": {
        "title": "条件型/数值未明",
        "description": "效果存在但当前 Step1 数值没有结构化出来，或只有 score_gain/exp_gain 这类语义标签。默认降权排序，供后续详情页/LLM 复查。",
        "metric_types": {"unknown_metric"},
        "max_header": "理论最大",
        "avg_header": "平均值",
    },
    "effect_boost": {
        "title": "经验/PT效果强化",
        "description": "经验、スコア、リンクボーナス、相关アクセサリー等收益技能的効果量増加。",
        "metric_types": {"effect_boost"},
        "max_header": "倍率最大",
        "avg_header": "倍率平均",
    },
}

EFFECT_LABELS = {
    "exp_gain": "経験値付与",
    "exp_distribution": "経験値分配",
    "exp_distribution_bonus": "経験値分配追加",
    "score_gain": "スコア獲得",
    "additional_score_gain": "追加スコア",
    "score_random_modifier": "スコア増減",
    "link_bonus": "リンクボーナス",
    "today_new_station_bonus": "今日の新駅ボーナス",
    "mile_gain": "マイル付与",
    "effect_multiplier": "効果量増加",
}

UNKNOWN_VALUE_TOKENS = {"score_gain", "exp_gain", "経験値付与", "スコア獲得"}

REPORT_LEVELS = base.REPORT_LEVELS
DEFAULT_LEVEL = base.DEFAULT_LEVEL


base.SCOPE_LABELS.update(
    {
        "front_car": "先头车",
        "accessing_denko": "访问中的でんこ",
        "accessed_denko": "被访问的でんこ",
    }
)
base.BASIS_LABELS.update(
    {
        "linked_station_count": "link站数",
        "same_theme_film_wearer_count": "同主题film着用数",
        "linked_denko_count": "link中でんこ数量",
    }
)


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def raw_detail_path(denko_id: str) -> Path:
    pool, _, number = denko_id.partition(":")
    return RAW_DIR / f"sample_detail_{pool}_{int(number):03d}.html"


def denko_level_from_text(text: str) -> str | None:
    match = re.search(r"でんこLv\.?\s*(\d+)", text)
    return match.group(1) if match else None


def expand_html_table(table: Any) -> list[list[str]]:
    matrix: list[list[str]] = []
    spans: dict[int, tuple[int, str]] = {}
    for tr in table.find_all("tr"):
        row: list[str] = []
        col = 0

        def fill_spans() -> None:
            nonlocal col
            while col in spans:
                remaining, text = spans[col]
                row.append(text)
                if remaining <= 1:
                    del spans[col]
                else:
                    spans[col] = (remaining - 1, text)
                col += 1

        fill_spans()
        for cell in tr.find_all(["th", "td"]):
            fill_spans()
            text = " ".join(cell.get_text(" ", strip=True).split())
            rowspan = int(cell.get("rowspan") or 1)
            colspan = int(cell.get("colspan") or 1)
            for offset in range(colspan):
                row.append(text)
                if rowspan > 1:
                    spans[col + offset] = (rowspan - 1, text)
            col += colspan
        fill_spans()
        if row:
            matrix.append(row)
    return matrix


def row_dict(headers: list[str], row: list[str]) -> dict[str, str]:
    return {headers[index] or f"column_{index}": row[index] for index in range(min(len(headers), len(row)))}


@lru_cache(maxsize=None)
def raw_detail_level_rows(denko_id: str) -> dict[str, dict[str, str]]:
    path = raw_detail_path(denko_id)
    if not path.exists():
        return {}
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    out: dict[str, dict[str, str]] = {}
    for table in soup.find_all("table"):
        matrix = expand_html_table(table)
        if not matrix:
            continue
        headers = matrix[0]
        if "スキルLv" not in headers or "効果" not in headers:
            continue
        for row in matrix[1:]:
            data = row_dict(headers, row)
            level = denko_level_from_text(data.get("スキルLv", ""))
            if not level:
                continue
            comment = data.get("コメント", "")
            # Prefer the full value row over the duplicated skill-name row.
            if level in out and comment.startswith("スキル名"):
                continue
            out[level] = data
    return out


@lru_cache(maxsize=None)
def raw_detail_aux_values(denko_id: str) -> dict[str, dict[str, str]]:
    path = raw_detail_path(denko_id)
    if not path.exists():
        return {}
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    out: dict[str, dict[str, str]] = {}
    for table in soup.find_all("table"):
        matrix = expand_html_table(table)
        if not matrix:
            continue
        headers = matrix[0]
        if not {"スコア獲得", "経験値付与"}.issubset(set(headers)):
            continue
        for row in matrix[1:]:
            data = row_dict(headers, row)
            level = denko_level_from_text(data.get("", "") or data.get("column_0", "") or data.get("スキルLv", ""))
            if not level:
                continue
            out[level] = {
                "score_gain": data.get("スコア獲得", ""),
                "exp_gain": data.get("経験値付与", ""),
            }
    return out


@lru_cache(maxsize=None)
def raw_detail_weekday_values(denko_id: str) -> dict[str, dict[str, dict[str, str]]]:
    path = raw_detail_path(denko_id)
    if not path.exists():
        return {}
    soup = BeautifulSoup(path.read_text(encoding="utf-8", errors="replace"), "html.parser")
    out: dict[str, dict[str, dict[str, str]]] = {}
    for table in soup.find_all("table"):
        matrix = expand_html_table(table)
        if len(matrix) < 3:
            continue
        days = matrix[0]
        effects = matrix[1]
        if not {"金曜日", "土曜日"}.intersection(days):
            continue
        if not {"スコア獲得", "経験値獲得"}.intersection(effects):
            continue
        headers = []
        for index, day in enumerate(days):
            effect = effects[index] if index < len(effects) else ""
            headers.append({"day": day, "effect": effect})
        for row in matrix[2:]:
            level = denko_level_from_text(row[0] if row else "")
            if not level:
                continue
            level_values: dict[str, dict[str, str]] = {}
            for index, cell in enumerate(row):
                if index >= len(headers):
                    continue
                day = headers[index]["day"]
                effect = headers[index]["effect"]
                if not day or not effect or not cell:
                    continue
                level_values.setdefault(day, {})[effect] = cell
            if level_values:
                out[level] = level_values
    return out


def is_positive_effect_multiplier(component: dict[str, Any]) -> bool:
    text = " ".join(
        str(component.get(key) or "")
        for key in ("condition_raw", "remarks_raw", "component_id")
    )
    return any(
        marker in text
        for marker in (
            "経験値",
            "スコア",
            "リンクボーナス",
            "リンク獲得",
            "リンク保持",
        )
    )


def value_with_level_meta(value: dict[str, Any], level: str) -> dict[str, Any]:
    out = dict(value)
    out["_report_level"] = level
    return out


def supplemental_value_from_raw_page(
    denko_id: str,
    component: dict[str, Any],
    value: dict[str, Any],
    level: str,
) -> dict[str, Any] | None:
    kind = str(component.get("effect_kind") or "")
    if kind not in {"exp_gain", "score_gain", "additional_score_gain"}:
        return None

    corrected = corrected_value_from_raw_row_effect(component, value)
    if corrected:
        return corrected

    weekday_value = supplemental_weekday_value_from_raw_page(denko_id, component, value, level)
    if weekday_value:
        return weekday_value

    raw = str(value.get("value_raw") or "")
    if raw not in UNKNOWN_VALUE_TOKENS and str(value.get("unit") or "") != "condition_only":
        return None

    aux = raw_detail_aux_values(denko_id).get(level, {})
    aux_value = aux.get(kind) or (aux.get("score_gain") if kind == "additional_score_gain" else None)
    if aux_value:
        aux_min, aux_max = parse_report_range(aux_value)
        return {
            **value,
            "unit": ("flat_exp_range" if aux_min != aux_max else "flat_exp") if kind == "exp_gain" else ("score_range" if aux_min != aux_max else "score"),
            "value_numeric": aux_min if aux_min == aux_max else None,
            "value_min": aux_min,
            "value_max": aux_max,
            "value_raw": ("経験値付与 " if kind == "exp_gain" else "スコア獲得 ") + aux_value,
            "report_supplemented_from": "detail_raw_aux_table",
        }

    raw_row = raw_detail_level_rows(denko_id).get(level, {})
    effect = raw_row.get("効果", "")
    if not effect:
        return None
    probability = {"発動率": raw_row.get("発動率", "")} if raw_row.get("発動率") else value.get("probability")

    if "スキル効果量" in effect and "スコア獲得" not in effect and "経験値付与" not in effect:
        return {
            **value,
            "unit": "report_ignore",
            "value_raw": effect,
            "report_supplemented_from": "detail_raw_skill_table",
        }

    random_match = re.search(r"スコア・経験値変動\s*([+＋-]?\d+(?:\.\d+)?\s*[％%]\s*[～〜~\-]\s*[+＋-]?\d+(?:\.\d+)?\s*[％%])", effect)
    if random_match:
        return {
            **value,
            "unit": "percent_range",
            "value_numeric": None,
            "value_raw": normalize_metric_raw(random_match.group(0)),
            "probability": probability,
            "report_supplemented_from": "detail_raw_skill_table",
        }

    combined_match = re.search(
        r"(?:経験値付与(?:＆|&|・)スコア獲得|スコア獲得(?:＆|&|・)経験値付与)\s*([+＋]?\d+(?:\.\d+)?(?:\s*[～〜~\-]\s*[+＋]?\d+(?:\.\d+)?)?)",
        effect,
    )
    if combined_match:
        raw_number = normalize_metric_raw(combined_match.group(1))
        return {
            **value,
            "unit": ("flat_exp_range" if "～" in raw_number or "~" in raw_number else "flat_exp") if kind == "exp_gain" else ("score_range" if "～" in raw_number or "~" in raw_number else "score"),
            "value_numeric": parse_report_number(raw_number),
            "value_min": parse_report_range(raw_number)[0],
            "value_max": parse_report_range(raw_number)[1],
            "value_raw": ("経験値付与 " if kind == "exp_gain" else "スコア獲得 ") + raw_number,
            "probability": probability,
            "report_supplemented_from": "detail_raw_skill_table",
        }

    ratio_match = re.search(
        r"(?:経験値付与(?:・|＆|&)?スコア獲得|スコア獲得(?:・|＆|&)?経験値付与|スコア獲得)[^0-9％%]*(?:与ダメージ|相手に与えたダメージ|受けたダメージ)の\s*(\d+(?:\.\d+)?)\s*[％%]",
        effect,
    )
    if ratio_match and (kind in {"exp_gain", "score_gain"}):
        value_number = ratio_match.group(1)
        return {
            **value,
            "unit": "percent",
            "value_numeric": parse_report_number(value_number),
            "value_raw": ("経験値付与 " if kind == "exp_gain" else "スコア獲得 ") + f"与ダメージの{value_number}%",
            "probability": probability,
            "report_supplemented_from": "detail_raw_skill_table",
        }
    return None


def supplemental_weekday_value_from_raw_page(
    denko_id: str,
    component: dict[str, Any],
    value: dict[str, Any],
    level: str,
) -> dict[str, Any] | None:
    if str(value.get("unit") or "") != "weekday_variable":
        return None
    weekday_map = {
        "friday": ("金曜日", "スコア獲得"),
        "saturday": ("土曜日", "経験値獲得"),
    }
    weekday = value.get("weekday")
    if weekday not in weekday_map:
        return None
    day_raw, effect_raw = weekday_map[str(weekday)]
    table_level = level if level in raw_detail_weekday_values(denko_id) else "80"
    cell = raw_detail_weekday_values(denko_id).get(table_level, {}).get(day_raw, {}).get(effect_raw)
    if not cell:
        return None
    value_min, value_max = parse_report_range(cell)
    kind = str(component.get("effect_kind") or "")
    prefix = "経験値獲得 " if kind == "exp_gain" else "スコア獲得 "
    suffix = f" ※曜日表Lv{table_level}基準" if table_level != level else ""
    return {
        **value,
        "unit": "flat_exp" if kind == "exp_gain" else "score",
        "value_numeric": value_min if value_min == value_max else None,
        "value_min": value_min,
        "value_max": value_max,
        "value_raw": prefix + cell + suffix,
        "report_supplemented_from": "detail_raw_weekday_table",
        "report_weekday_table_level": table_level,
    }


def corrected_value_from_raw_row_effect(component: dict[str, Any], value: dict[str, Any]) -> dict[str, Any] | None:
    raw_row = value.get("raw_row") or {}
    effect = str(raw_row.get("効果") or "")
    if not effect:
        return None
    kind = str(component.get("effect_kind") or "")
    label = str(component.get("condition_label") or "")
    label_prefix = re.escape(label) + r"\s*" if label else r"(?:\(\d+\)\s*)?"
    value_token = r"(?:[+＋]?\d+(?:\.\d+)?\s*体につき\s*[+＋]?\d+(?:\.\d+)?|[+＋]?\d+(?:\.\d+)?(?:\s*[～〜~\-]\s*[+＋]?\d+(?:\.\d+)?)?)"
    if kind == "exp_gain":
        patterns = [
            rf"{label_prefix}(?:追加)?経験値付与\s*({value_token})",
            rf"{label_prefix}(?:経験値付与(?:＆|&|・)スコア獲得|スコア獲得(?:＆|&|・)経験値付与)\s*({value_token})",
        ]
        prefix = "経験値付与 "
        unit = "flat_exp"
    elif kind in {"score_gain", "additional_score_gain"}:
        patterns = [
            rf"{label_prefix}(?:追加)?スコア獲得\s*({value_token})",
            rf"{label_prefix}(?:経験値付与(?:＆|&|・)スコア獲得|スコア獲得(?:＆|&|・)経験値付与)\s*({value_token})",
        ]
        prefix = "スコア獲得 "
        unit = "score"
    else:
        return None

    for pattern in patterns:
        match = re.search(pattern, effect)
        if not match:
            continue
        raw_number = normalize_metric_raw(match.group(1))
        if raw_number == str(value.get("value_raw") or "").replace(prefix, ""):
            return None
        value_min, value_max = metric_range_from_raw_number(raw_number)
        return {
            **value,
            "unit": (unit + "_range") if value_min != value_max else unit,
            "value_numeric": value_min if value_min == value_max else None,
            "value_min": value_min,
            "value_max": value_max,
            "value_raw": prefix + raw_number,
            "report_supplemented_from": "raw_row_effect_correction",
        }
    return None


def effective_value(denko_id: str, component: dict[str, Any], value: dict[str, Any], level: str) -> dict[str, Any]:
    supplement = supplemental_value_from_raw_page(denko_id, component, value, level)
    return value_with_level_meta(supplement or value, level)


def normalize_metric_raw(text: str) -> str:
    return text.replace("＋", "+").replace("％", "%").replace("〜", "～").strip()


def parse_report_range(text: str) -> tuple[float | None, float | None]:
    nums = signed_numbers(normalize_metric_raw(text))
    if not nums:
        return None, None
    if any(mark in text for mark in ("～", "~", "-")) and len(nums) >= 2:
        return min(nums), max(nums)
    return nums[0], nums[0]


def metric_range_from_raw_number(text: str) -> tuple[float | None, float | None]:
    normalized = normalize_metric_raw(text)
    per_unit = re.search(r"につき\s*([+＋]?\d+(?:\.\d+)?)", normalized)
    if per_unit:
        value = float(per_unit.group(1))
        return value, value
    return parse_report_range(normalized)


def parse_report_number(text: str) -> float | None:
    nums = signed_numbers(normalize_metric_raw(text))
    return nums[0] if nums else None


def value_for_metric_type(denko_id: str, component: dict[str, Any]) -> dict[str, Any]:
    values = component.get("values_by_denko_level") or {}
    if DEFAULT_LEVEL in values:
        return effective_value(denko_id, component, values[DEFAULT_LEVEL], DEFAULT_LEVEL)
    fallback_level, fallback_value = base.basis_value(component)
    return effective_value(denko_id, component, fallback_value, fallback_level) if fallback_value else fallback_value


def has_numeric_value(value: dict[str, Any]) -> bool:
    return any(base.as_number(value.get(key)) is not None for key in ("value_numeric", "value_min", "value_max"))


def is_percent_or_ratio(value: dict[str, Any]) -> bool:
    raw = str(value.get("value_raw") or "")
    unit = str(value.get("unit") or "")
    return (
        "percent" in unit
        or "random_percent" in unit
        or "%" in raw
        or "％" in raw
        or "受けたダメージ" in raw
        or "与ダメージ" in raw
    )


def metric_type(component: dict[str, Any], value: dict[str, Any]) -> str:
    kind = str(component.get("effect_kind") or "")
    raw = str(value.get("value_raw") or "")
    unit = str(value.get("unit") or "")

    if unit == "report_ignore":
        return "ignore"
    if kind == "effect_multiplier":
        return "effect_boost" if is_positive_effect_multiplier(component) else "ignore"
    if kind in {"link_bonus", "today_new_station_bonus", "mile_gain"}:
        return "bonus_gain"
    if kind in {"exp_distribution", "exp_distribution_bonus"}:
        return "exp_ratio"
    if kind == "exp_gain":
        if raw in UNKNOWN_VALUE_TOKENS or unit == "condition_only":
            return "unknown_metric"
        if is_percent_or_ratio(value):
            return "exp_ratio"
        return "fixed_exp" if has_numeric_value(value) else "unknown_metric"
    if kind in {"score_gain", "additional_score_gain", "score_random_modifier"}:
        if raw in UNKNOWN_VALUE_TOKENS or unit == "condition_only":
            return "unknown_metric"
        if kind == "score_random_modifier" or is_percent_or_ratio(value):
            return "score_percent_modifier"
        return "fixed_score" if has_numeric_value(value) else "unknown_metric"
    return "ignore"


def component_metric_type(denko_id: str, component: dict[str, Any]) -> str:
    value = value_for_metric_type(denko_id, component)
    return metric_type(component, value) if value else "ignore"


def belongs_to_tab(tab_id: str, denko_id: str, component: dict[str, Any]) -> bool:
    return component_metric_type(denko_id, component) in TABS[tab_id]["metric_types"]


def signed_numbers(text: str) -> list[float]:
    out = []
    for raw in re.findall(r"[+-]?\d+(?:\.\d+)?", text.replace("％", "%")):
        try:
            out.append(float(raw))
        except ValueError:
            pass
    return out


def percent_range(raw: str) -> tuple[float | None, float | None]:
    if "%" not in raw and "％" not in raw:
        return None, None
    nums = signed_numbers(raw)
    if not nums:
        return None, None
    if any(mark in raw for mark in ("～", "~", "or")):
        return min(nums), max(nums)
    positives = [num for num in nums if num >= 0]
    value = max(positives or nums, key=abs)
    return value, value


def multiplier_value(raw: str, numeric: float | None) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\s*倍", raw)
    if match:
        return float(match.group(1))
    return numeric


def probability_text(value: dict[str, Any]) -> str:
    probability = value.get("probability")
    if not probability:
        return "-"
    if isinstance(probability, dict):
        labels = {"activation_probability": "発動率"}
        parts = []
        for key, item in probability.items():
            if item in {None, "", "-"}:
                continue
            label = labels.get(str(key), str(key))
            if label == "発動率":
                parts.append(str(item))
            else:
                parts.append(f"{label} {item}")
        return " / ".join(parts) if parts else "-"
    return str(probability)


def value_range(component: dict[str, Any], value: dict[str, Any], metric: str) -> tuple[float | None, float | None]:
    if metric == "unknown_metric":
        return None, None
    raw = str(value.get("value_raw") or "")
    unit = str(value.get("unit") or "")
    numeric = base.as_number(value.get("value_numeric"))
    value_min = base.as_number(value.get("value_min"))
    value_max = base.as_number(value.get("value_max"))

    if unit == "multiplier":
        factor = multiplier_value(raw, numeric)
        return (factor, factor) if factor is not None else (None, None)
    if "percent" in unit or "%" in raw or "％" in raw:
        pmin, pmax = percent_range(raw)
        if pmax is not None:
            return pmin, pmax
    if value_min is not None and value_max is not None:
        return min(value_min, value_max), max(value_min, value_max)
    if value_max is not None:
        return 0.0 if "～" in raw or "~" in raw else value_max, value_max
    if numeric is not None:
        return numeric, numeric
    return None, None


def mean_value(value_min: float | None, value_max: float | None) -> float | None:
    if value_min is None or value_max is None:
        return None
    return (value_min + value_max) / 2


def metric_text(metric: str, value: float | None) -> str:
    if value is None:
        return "-"
    if metric == "effect_boost":
        return f"{value:g}倍"
    if metric in {"exp_ratio", "score_percent_modifier"}:
        sign = "+" if value > 0 else ""
        return f"{sign}{value:g}%"
    return f"{value:g}"


def display_metric_text(metric: str, value: float | None, value_raw: str) -> str:
    text = metric_text(metric, value)
    if value is not None and "につき" in value_raw:
        return f"{text}/体"
    return text


def level_value_text(level: str, value: dict[str, Any], metric: str) -> str:
    raw = str(value.get("value_raw") or "-")
    if metric == "unknown_metric":
        raw = "数值未明" if raw in UNKNOWN_VALUE_TOKENS else f"数值未明（{raw}）"
    return raw if level == DEFAULT_LEVEL else f"※Lv{level}: {raw}"


def level_metrics(denko_id: str, component: dict[str, Any], level: str, component_metric: str) -> dict[str, Any] | None:
    values = component.get("values_by_denko_level") or {}
    source_value = values.get(level)
    if not source_value:
        return None
    value = effective_value(denko_id, component, source_value, level)
    metric = component_metric if component_metric != "ignore" else metric_type(component, value)
    value_min, value_max = value_range(component, value, metric)
    avg_value = mean_value(value_min, value_max)
    value_raw = str(value.get("value_raw") or "")
    return {
        "level": level,
        "metric_type": metric,
        "sort_max": value_max,
        "sort_avg": avg_value,
        "value_text": level_value_text(level, value, metric),
        "max_text": display_metric_text(metric, value_max, value_raw),
        "avg_text": display_metric_text(metric, avg_value, value_raw),
        "probability": probability_text(value),
        "duration": value.get("duration") or "-",
        "cooldown": value.get("cooldown") or "-",
        "supplemented": bool(value.get("report_supplemented_from")),
    }


def target_text(component: dict[str, Any]) -> str:
    target = base.target_text(component)
    if component.get("target_scope"):
        return target
    condition = str(component.get("condition_raw") or "")
    if "相手に経験値" in condition or "相手にスコア" in condition:
        return "相手でんこ"
    if "アクセスしたでんこ" in condition:
        return "访问中的でんこ"
    if "編成内" in condition:
        return "编成内全员"
    return target


def condition_text(component: dict[str, Any]) -> str:
    condition = str(component.get("condition_raw") or "")
    filters = component.get("target_filters") or {}
    attribute = filters.get("attribute")
    if not attribute:
        match = re.search(r"\s(heat|cool|eco)属性", condition)
        attribute = match.group(1) if match else None
    if attribute and "編成内の が" in condition:
        condition = condition.replace("編成内の が", f"編成内の{attribute}属性でんこが")
        condition = re.sub(rf"\s{re.escape(str(attribute))}属性(?=$|[\s　])", "", condition)
    return condition


def build_candidates(tab_id: str, rows: list[dict[str, Any]], metadata: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    candidates = []
    for row in rows:
        denko_id = str(row.get("denko_id") or "")
        for component in row.get("skill_components") or []:
            if not belongs_to_tab(tab_id, denko_id, component):
                continue
            component_metric = component_metric_type(denko_id, component)
            levels = {
                level: metrics
                for level in REPORT_LEVELS
                if (metrics := level_metrics(denko_id, component, level, component_metric)) is not None
            }
            if not levels:
                continue
            fallback_level, _fallback_value = base.basis_value(component)
            if DEFAULT_LEVEL in levels:
                initial_level = DEFAULT_LEVEL
            elif fallback_level in levels:
                initial_level = fallback_level
            else:
                initial_level = next(iter(levels))
            initial = levels[initial_level]
            group_id, group_label = base.activation_group(row, component)
            denko_meta = metadata.get(denko_id, {})
            target = target_text(component)
            filters = base.compact_filter_text(component)
            condition = condition_text(component)
            all_level_text = " ".join(str(metrics["value_text"]) for metrics in levels.values())
            search = " ".join(
                [
                    denko_id,
                    str(row.get("name") or ""),
                    str(denko_meta.get("attribute") or ""),
                    str(denko_meta.get("type_key") or ""),
                    str(component.get("component_id") or ""),
                    condition,
                    target,
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
                    "metric_type": component_metric,
                    "kind": component.get("effect_kind"),
                    "component_id": component.get("component_id"),
                    "condition": condition,
                    "target": target,
                    "filters": filters,
                    "activation_group": group_id,
                    "activation_label": group_label,
                    "activation_type": component.get("activation_type") or row.get("activation_type") or "",
                    "probability": initial["probability"],
                    "duration": initial["duration"],
                    "cooldown": initial["cooldown"],
                    "level_value": initial["value_text"],
                    "max_text": initial["max_text"],
                    "avg_text": initial["avg_text"],
                    "level_data": json.dumps(levels, ensure_ascii=False, separators=(",", ":")),
                    "vu_only": base.is_vu_only(component, fallback_level),
                    "needs_metric_review": component_metric == "unknown_metric",
                    "supplemented": any(bool(metrics.get("supplemented")) for metrics in levels.values()),
                    "url": row.get("detail_url") or "",
                    "search": search,
                }
            )
    candidates.sort(
        key=lambda item: (
            -(item["sort_max"] if item["sort_max"] is not None else -1),
            base.denko_sort_key(str(item["denko_id"])),
            str(item["component_id"]),
        )
    )
    return candidates


def render_rows(tab_id: str, candidates: list[dict[str, Any]]) -> str:
    rows = []
    for rank, item in enumerate(candidates, 1):
        badges = []
        if item["needs_metric_review"]:
            badges.append('<span class="badge">数值未明</span>')
        if item["supplemented"]:
            badges.append('<span class="badge badge-supplement">网页补完</span>')
        badge = (" " + " ".join(badges)) if badges else ""
        rows.append(
            "\n".join(
                [
                    f'<tr data-tab="{esc(tab_id)}" data-search="{esc(item["search"])}" data-activation="{esc(item["activation_group"])}" data-attr="{esc(item["attribute"])}" data-type="{esc(item["type_key"])}" data-metric-type="{esc(item["metric_type"])}" data-needs-metric-review="{str(item["needs_metric_review"]).lower()}" data-vu-only="{str(item["vu_only"]).lower()}" data-sort-max="{item["sort_max"] if item["sort_max"] is not None else -1}" data-sort-avg="{item["sort_avg"] if item["sort_avg"] is not None else -1}" data-levels="{esc(item["level_data"])}">',
                    f'<td class="rank">{rank}</td>',
                    f'<td><strong>{esc(item["denko_id"])}</strong><br><a href="{esc(item["url"])}">{esc(item["name"])}</a></td>',
                    f'<td>{esc(item["attribute"])}</td>',
                    f'<td>{esc(item["type_key"])}</td>',
                    f'<td>{esc(EFFECT_LABELS.get(str(item["kind"]), item["kind"]))}{badge}<br><span class="muted">{esc(item["component_id"])}</span></td>',
                    f'<td class="metric max-cell">{esc(item["max_text"])}</td>',
                    f'<td class="metric avg-cell">{esc(item["avg_text"])}</td>',
                    f'<td class="level-cell">{esc(item["level_value"])}</td>',
                    f'<td class="probability-cell">{esc(item["probability"])}</td>',
                    f'<td class="duration-cell">{esc(item["duration"])}</td>',
                    f'<td class="cooldown-cell">{esc(item["cooldown"])}</td>',
                    f'<td title="{esc(item["activation_type"])}">{esc(item["activation_label"])}</td>',
                    f'<td>{esc(item["target"])}<br><span class="muted">{esc(item["filters"])}</span></td>',
                    f'<td>{esc(item["condition"])}</td>',
                    "</tr>",
                ]
            )
        )
    return "".join(rows)


def render_table(tab_id: str, candidates: list[dict[str, Any]]) -> str:
    tab = TABS[tab_id]
    return f"""
    <section class="tab-panel" id="panel-{esc(tab_id)}" data-tab-panel="{esc(tab_id)}">
      <h2>{esc(tab["title"])} <span class="muted">({len(candidates)})</span></h2>
      <p>{esc(tab["description"])}</p>
      <table>
        <thead>
          <tr>
            <th>排行</th>
            <th>でんこ</th>
            <th>属性</th>
            <th>类型</th>
            <th>效果</th>
            <th>{esc(tab["max_header"])}</th>
            <th>{esc(tab["avg_header"])}</th>
            <th>等级值</th>
            <th>概率</th>
            <th>持续</th>
            <th>CD</th>
            <th>发动</th>
            <th>对象/限制</th>
            <th>触发与条件</th>
          </tr>
        </thead>
        <tbody>{render_rows(tab_id, candidates)}</tbody>
      </table>
    </section>
    """


def main() -> None:
    rows = base.read_jsonl(SKILL_PATH)
    metadata = base.denko_metadata()
    candidates_by_tab = {tab_id: build_candidates(tab_id, rows, metadata) for tab_id in TABS}
    tab_buttons = "\n".join(
        f'<button class="tab-button" type="button" data-tab="{esc(tab_id)}">{esc(tab["title"])} <span>{len(candidates_by_tab[tab_id])}</span></button>'
        for tab_id, tab in TABS.items()
    )
    sections = "\n".join(render_table(tab_id, candidates_by_tab[tab_id]) for tab_id in TABS)
    counts = {tab_id: len(candidates) for tab_id, candidates in candidates_by_tab.items()}

    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Ekimemo Step2 经验/PT辅助排行</title>
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
    .toggle {{ display: inline-flex; align-items: center; gap: 5px; font-size: 13px; color: #444c56; }}
    .toggle input {{ padding: 0; }}
    .badge {{ display: inline-block; margin-left: 6px; padding: 1px 5px; border: 1px solid #d0a215; border-radius: 4px; color: #7d5f00; background: #fff8c5; font-size: 11px; white-space: nowrap; }}
    .badge-supplement {{ border-color: #6fdd8b; color: #116329; background: #dafbe1; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin-top: 12px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 7px 8px; vertical-align: top; }}
    th {{ background: #f6f8fa; position: sticky; top: 53px; z-index: 2; }}
    td:nth-child(10), td:nth-child(11), td:nth-child(12) {{ white-space: nowrap; }}
    td:nth-child(14) {{ min-width: 260px; }}
    .metric {{ min-width: 108px; }}
    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}
    a {{ color: #0969da; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <h1>Ekimemo Step2 经验/PT辅助排行</h1>
  <p>从 Step1 DB 自动整理，分类参考 wiki「経験値、スコア系スキル」。固定值、百分比/倍率、条件型数值未明分开排行；默认按 Lv50 查看，可切换 Lv30/Lv80/Lv92/Lv100；仅 VU 后生效的项目默认隐藏。</p>
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
    <select id="sortMode">
      <option value="max">按理论最大排序</option>
      <option value="avg">按平均值排序</option>
    </select>
    <select id="activation">
      <option value="">全部发动</option>
      <option value="always">常驻</option>
      <option value="manual">手动</option>
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
    <label class="toggle"><input id="showVu" type="checkbox">显示仅VU后生效</label>
  </div>
  {sections}
  <script>
    const state = {{ activeTab: 'fixed_exp' }};
    const q = document.getElementById('q');
    const levelMode = document.getElementById('levelMode');
    const sortMode = document.getElementById('sortMode');
    const activation = document.getElementById('activation');
    const attr = document.getElementById('attr');
    const type = document.getElementById('type');
    const showVu = document.getElementById('showVu');
    const tabButtons = [...document.querySelectorAll('.tab-button')];
    const panels = [...document.querySelectorAll('[data-tab-panel]')];
    const rowCache = new Map();

    for (const panel of panels) {{
      const rows = [...panel.querySelectorAll('tbody tr')];
      for (const row of rows) {{
        try {{
          row.levels = JSON.parse(row.dataset.levels || '{{}}');
        }} catch (_error) {{
          row.levels = {{}};
        }}
      }}
      rowCache.set(panel.dataset.tabPanel, rows);
    }}

    function activeRows() {{
      return rowCache.get(state.activeTab) || [];
    }}

    function applyLevel(row) {{
      const data = row.levels[levelMode.value];
      row.dataset.hasLevel = data ? 'true' : 'false';
      row.dataset.sortMax = data && data.sort_max !== null ? data.sort_max : -1;
      row.dataset.sortAvg = data && data.sort_avg !== null ? data.sort_avg : -1;
      row.querySelector('.max-cell').textContent = data ? data.max_text : '-';
      row.querySelector('.avg-cell').textContent = data ? data.avg_text : '-';
      row.querySelector('.level-cell').textContent = data ? data.value_text : '-';
      row.querySelector('.probability-cell').textContent = data ? data.probability : '-';
      row.querySelector('.duration-cell').textContent = data ? data.duration : '-';
      row.querySelector('.cooldown-cell').textContent = data ? data.cooldown : '-';
    }}

    function sortActiveRows() {{
      const rows = activeRows();
      for (const row of rows) applyLevel(row);
      const key = sortMode.value === 'avg' ? 'sortAvg' : 'sortMax';
      rows.sort((a, b) => Number(b.dataset[key]) - Number(a.dataset[key]));
      const tbody = document.querySelector(`#panel-${{state.activeTab}} tbody`);
      for (const row of rows) tbody.appendChild(row);
    }}

    function applyFilter() {{
      const needle = q.value.trim().toLowerCase();
      sortActiveRows();
      let visibleRank = 1;
      for (const row of activeRows()) {{
        const okText = !needle || row.dataset.search.includes(needle);
        const okActivation = !activation.value || row.dataset.activation === activation.value;
        const okAttr = !attr.value || row.dataset.attr === attr.value;
        const okType = !type.value || row.dataset.type === type.value;
        const okVu = showVu.checked || row.dataset.vuOnly !== 'true';
        const okLevel = row.dataset.hasLevel === 'true';
        const visible = okText && okActivation && okAttr && okType && okVu && okLevel;
        row.style.display = visible ? '' : 'none';
        if (visible) row.querySelector('.rank').textContent = visibleRank++;
      }}
    }}

    function setActiveTab(tabId) {{
      state.activeTab = tabId;
      for (const button of tabButtons) button.classList.toggle('active', button.dataset.tab === tabId);
      for (const panel of panels) panel.classList.toggle('active', panel.dataset.tabPanel === tabId);
      applyFilter();
    }}

    for (const button of tabButtons) {{
      button.addEventListener('click', () => setActiveTab(button.dataset.tab));
    }}
    for (const input of [q, levelMode, sortMode, activation, attr, type, showVu]) {{
      input.addEventListener('input', applyFilter);
    }}
    setActiveTab(state.activeTab);
  </script>
</body>
</html>
"""
    html_text = "\n".join(line.rstrip() for line in html_text.splitlines()) + "\n"
    OUT_HTML.write_text(html_text, encoding="utf-8")
    print(json.dumps({"out": str(OUT_HTML.relative_to(ROOT)), "counts": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
