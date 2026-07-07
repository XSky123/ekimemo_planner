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
    "nullification": {
        "title": "无效化/强制结束",
        "description": "只收技能无效化、伤害无效化、バッテリー不可、スキル强制结束等机制，不收普通攻防增减。",
    },
    "effect_boost": {
        "title": "效果量强化",
        "description": "只收“强化别的技能/饰品/フィルム效果量”的技能，例如 ATK/DEF 技能效果量、经验技能效果量、アクセサリー/フィルム效果量。",
    },
    "cooldown_probability": {
        "title": "CD/概率操作",
        "description": "只收改变其他技能发动率、重置/缩短 CD 的技能。不把普通技能随等级成长导致的概率变化算进来。",
    },
    "condition_weekday": {
        "title": "条件：星期",
        "description": "以曜日为条件或效果分支的技能。",
    },
    "condition_month": {
        "title": "条件：月份/季节",
        "description": "以月份、季节或特定月段为条件或效果分支的技能。",
    },
    "condition_weather": {
        "title": "条件：天气",
        "description": "以天気、晴/雨/雪/曇等天气状态为条件的技能。",
    },
    "condition_temperature": {
        "title": "条件：温度",
        "description": "以気温、温度、℃区间为条件的技能。",
    },
    "condition_link": {
        "title": "条件：link数/时间",
        "description": "以リンク駅数、リンク時間、最大 link 时间等为条件或倍率依据的技能。",
    },
    "event_access": {
        "title": "活动/访问次数",
        "description": "只收额外访问、随机访问、传送/访问已访问站、新駅/今日の新駅、检测范围和访问回数相关技能。",
    },
}

EFFECT_LABELS = {
    **base.EFFECT_LABELS,
    "activation_probability_boost": "发动率强化",
    "battery_disable": "バッテリー不可",
    "cooldown_reduction": "CD缩短",
    "cooldown_reset": "CD解除",
    "damage_nullification": "伤害无效化",
    "effect_multiplier": "效果量强化",
    "film_effect_multiplier": "フィルム效果强化",
    "film_series_effect_boost": "フィルム系列强化",
    "force_hp_zero": "强制HP归零",
    "link_bonus": "linkボーナス",
    "link_transfer": "link转移",
    "memory_access_station_count": "访问记录站数",
    "memory_access_time": "访问记录时间",
    "mile_gain": "mile付与",
    "random_previous_station_access": "随机访问已访问站",
    "remote_station_access": "远程访问",
    "skill_disable": "技能无效化",
    "skill_force_end": "技能强制结束",
    "station_link_transfer": "link转让",
    "today_new_station_bonus": "今日の新駅ボーナス",
}

NULLIFICATION_KINDS = {
    "battery_disable",
    "damage_nullification",
    "skill_disable",
    "skill_force_end",
}
EFFECT_BOOST_KINDS = {
    "effect_multiplier",
    "film_effect_multiplier",
    "film_series_effect_boost",
}
COOLDOWN_PROBABILITY_KINDS = {
    "activation_probability_boost",
    "cooldown_reduction",
    "cooldown_reset",
}
EVENT_ACCESS_KINDS = {
    "extra_access",
    "link_bonus",
    "link_transfer",
    "memory_access_station_count",
    "memory_access_time",
    "mile_gain",
    "radar_detection_range",
    "random_previous_station_access",
    "remote_station_access",
    "station_link_transfer",
    "today_new_station_bonus",
}

CONDITION_PATTERNS = {
    "condition_weekday": re.compile(r"曜日|月曜日|火曜日|水曜日|木曜日|金曜日|土曜日|日曜日"),
    "condition_month": re.compile(r"(?:[1-9]|1[0-2])月|季節|春|夏|秋|冬"),
    "condition_weather": re.compile(r"天気|晴|雨|雪|曇"),
    "condition_temperature": re.compile(r"気温|温度|℃|°C|\d+度"),
    "condition_link": re.compile(r"リンク(?:駅数|時間)|最大リンク|最も長いリンク時間|link(?:駅数|時間)|リンクしている.+駅数"),
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
    pattern = CONDITION_PATTERNS[tab_id]
    text = component_text(component, include_level_values=True)
    return bool(pattern.search(text))


def belongs_to_tab(tab_id: str, row: dict[str, Any], component: dict[str, Any]) -> bool:
    kind = str(component.get("effect_kind") or "")
    if tab_id == "nullification":
        return kind in NULLIFICATION_KINDS
    if tab_id == "effect_boost":
        return kind in EFFECT_BOOST_KINDS
    if tab_id == "cooldown_probability":
        return kind in COOLDOWN_PROBABILITY_KINDS
    if tab_id in CONDITION_PATTERNS:
        return condition_hit(tab_id, row, component)
    if tab_id == "event_access":
        return kind in EVENT_ACCESS_KINDS
    return False


def signed_numbers(text: str) -> list[float]:
    out = []
    for raw in re.findall(r"[+-]?\d+(?:\.\d+)?", text.replace("％", "%")):
        try:
            out.append(float(raw))
        except ValueError:
            pass
    return out


def metric_value(tab_id: str, value: dict[str, Any]) -> float | None:
    if tab_id == "nullification":
        return None
    raw = str(value.get("value_raw") or "")
    numeric_text = raw.split("※", 1)[0]
    numeric = base.as_number(value.get("value_numeric"))
    if numeric is not None:
        return numeric
    if "クールタイム解除" in raw or "CD解除" in raw:
        return 999.0
    if tab_id == "cooldown_probability" and re.search(r"クールタイム|CD", raw):
        nums = signed_numbers(numeric_text)
        return max((abs(num) for num in nums), default=None)
    if "倍" in numeric_text:
        nums = signed_numbers(numeric_text)
        return max(nums) if nums else None
    if "%" in numeric_text or "％" in numeric_text:
        nums = signed_numbers(numeric_text)
        return max(nums) if nums else None
    nums = signed_numbers(numeric_text)
    return max(nums) if nums else None


def level_value_text(level: str, value: dict[str, Any]) -> str:
    raw = base.clean_display_text(value.get("value_raw") or "-")
    return f"Lv{level}: {raw}" if level != DEFAULT_LEVEL else raw


def level_metrics(tab_id: str, component: dict[str, Any], level: str) -> dict[str, Any] | None:
    values = component.get("values_by_denko_level") or {}
    value = values.get(level)
    if not value:
        return None
    metric = metric_value(tab_id, value)
    expected = metric * base.probability_factor(value) / 100 if metric is not None else None
    metric_text = "-" if metric is None else f"{metric:g}"
    expected_text = "-" if expected is None else f"{expected:g}"
    return {
        "level": level,
        "sort_max": metric,
        "sort_avg": expected,
        "value_text": level_value_text(level, value),
        "max_text": metric_text,
        "avg_text": expected_text,
        "probability": base.probability_text(value),
        "duration": value.get("duration") or "-",
        "cooldown": value.get("cooldown") or "-",
    }


def target_text(component: dict[str, Any]) -> str:
    target = base.target_text(component)
    target = re.sub(r"component:[\w_]+", "关联效果", target)
    target = re.sub(r"(关联效果)(?:、关联效果)+", r"\1", target)
    return target


def condition_text(row: dict[str, Any], component: dict[str, Any]) -> str:
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
            condition = condition_text(row, component)
            filters = base.compact_filter_text(component)
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
                }
            )
    candidates.sort(
        key=lambda item: (
            -(item["sort_avg"] if item["sort_avg"] is not None else -1),
            base.denko_sort_key(str(item["denko_id"])),
            str(item["component_id"]),
        )
    )
    return candidates


def render_rows(tab_id: str, candidates: list[dict[str, Any]]) -> str:
    rows = []
    for rank, item in enumerate(candidates, 1):
        component_label = base.component_display_label(item["component_id"], item["kind"])
        component_html = f'<br><span class="muted">{esc(component_label)}</span>' if component_label else ""
        rows.append(
            "\n".join(
                [
                    f'<tr data-tab="{esc(tab_id)}" data-search="{esc(item["search"])}" data-activation="{esc(item["activation_group"])}" data-attr="{esc(item["attribute"])}" data-type="{esc(item["type_key"])}" data-vu-only="{str(item["vu_only"]).lower()}" data-sort-max="{item["sort_max"] if item["sort_max"] is not None else -1}" data-sort-avg="{item["sort_avg"] if item["sort_avg"] is not None else -1}" data-levels="{esc(item["level_data"])}">',
                    f'<td class="rank">{rank}</td>',
                    f'<td><strong>{esc(item["denko_id"])}</strong><br><a href="{esc(item["url"])}">{esc(item["name"])}</a></td>',
                    f'<td>{esc(item["attribute"])}</td>',
                    f'<td>{esc(item["type_key"])}</td>',
                    f'<td>{esc(EFFECT_LABELS.get(str(item["kind"]), str(item["kind"])))}{component_html}</td>',
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
            <th>理论最大</th>
            <th>期望值</th>
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
    candidates_by_tab_all = {tab_id: build_candidates(tab_id, rows, metadata) for tab_id in TABS}
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
    td:nth-child(10), td:nth-child(11), td:nth-child(12) {{ white-space: nowrap; }}
    td:nth-child(14) {{ min-width: 280px; }}
    .metric {{ min-width: 108px; }}
    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}
    a {{ color: #0969da; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <h1>Ekimemo Step2 技能工具索引</h1>
  <p>严格按机制整理：无效化/强制结束、效果量强化、CD/概率操作、明确条件索引、活动/访问次数。普通 ATK/DEF/経験値/スコア 增减不会进入前三类工具 tab。</p>
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
  {base.interactive_script(default_tab)}
</body>
</html>
"""
    html_text = "\n".join(line.rstrip() for line in html_text.splitlines()) + "\n"
    base.write_text_lf(OUT_HTML, html_text)
    print(json.dumps({"out": str(OUT_HTML.relative_to(ROOT)), "counts": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
