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
OUT_HTML = ROOT / "data" / "reports" / "step2_mobility_visit_rankings_zh.html"


TABS = {
    "extra_access": {
        "title": "追加访问/再次访问",
        "description": "直接增加一次访问、失败后再访问、同一站追加访问。它们是行为效果，不把“再访问一次”伪装成可比较的理论收益。",
        "kinds": {"extra_access"},
    },
    "random_remote_access": {
        "title": "随机/远程/思い出し访问",
        "description": "随机访问已取得站、远程访问常用站周边、增加思い出しアクセス次数或时间。适合人在固定地点时补访问机会。",
        "kinds": {"random_previous_station_access", "remote_station_access", "memory_access_station_count", "memory_access_time"},
    },
    "range_transfer": {
        "title": "范围/链接转移",
        "description": "レーダー范围、link 转移、站点受け渡し。它们未必增加访问次数，但会改变可触达范围或保留/转移访问成果。",
        "kinds": {"radar_detection_range", "station_link_transfer", "link_transfer"},
    },
    "new_station_bonus": {
        "title": "今日新駅奖励",
        "description": "今日新駅ボーナス增幅。不是访问次数增加，但和长距离开图、活动路线收益有关，单独列出。",
        "kinds": {"today_new_station_bonus"},
    },
}


EFFECT_LABELS = {
    "extra_access": "追加访问",
    "random_previous_station_access": "随机已访问站",
    "remote_station_access": "远程/常用站周边访问",
    "memory_access_station_count": "思い出し访问次数",
    "memory_access_time": "思い出し时间",
    "radar_detection_range": "レーダー范围",
    "station_link_transfer": "link譲渡",
    "link_transfer": "link转移",
    "today_new_station_bonus": "今日新駅奖励",
}


KIND_USE_CASE = {
    "extra_access": "回数活动核心",
    "random_previous_station_access": "固定地点补访问",
    "remote_station_access": "回国/固定地点补站",
    "memory_access_station_count": "思い出し回数扩展",
    "memory_access_time": "思い出し窗口延长",
    "radar_detection_range": "扩大可访问范围",
    "station_link_transfer": "转移link成果",
    "link_transfer": "保留/转移link",
    "today_new_station_bonus": "开图收益放大",
}

NON_NUMERIC_ACCESS_KINDS = {
    "extra_access",
    "random_previous_station_access",
    "remote_station_access",
}


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def probability_text(value: dict[str, Any]) -> str:
    return base.probability_text(value)


def probability_max(value: dict[str, Any]) -> float:
    probability = value.get("probability")
    if not probability:
        return 100.0
    text = json.dumps(probability, ensure_ascii=False) if isinstance(probability, dict) else str(probability)
    nums = [float(raw) for raw in re.findall(r"\d+(?:\.\d+)?", text)]
    if not nums:
        return 100.0
    return min(max(nums), 100.0)


def numeric_from_text(text: str) -> float | None:
    nums = [float(raw) for raw in re.findall(r"[+-]?\d+(?:\.\d+)?", text.replace("％", "%"))]
    return max(nums, key=abs) if nums else None


def duration_minutes(raw: str) -> float | None:
    hour_match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*時間", raw)
    minute_match = re.search(r"([+-]?\d+(?:\.\d+)?)\s*分", raw)
    if not hour_match and not minute_match:
        return None
    hours = float(hour_match.group(1)) if hour_match else 0.0
    minutes = float(minute_match.group(1)) if minute_match else 0.0
    return hours * 60 + minutes


def value_range(kind: str, value: dict[str, Any]) -> tuple[float | None, float | None]:
    if kind in NON_NUMERIC_ACCESS_KINDS:
        return None, None
    raw = str(value.get("value_raw") or "")
    if kind == "memory_access_time":
        minutes = duration_minutes(raw)
        return (minutes, minutes) if minutes is not None else (None, None)
    value_min = base.as_number(value.get("value_min"))
    value_max = base.as_number(value.get("value_max"))
    if value_min is not None and value_max is not None:
        return min(abs(value_min), abs(value_max)), max(abs(value_min), abs(value_max))
    numeric = base.as_number(value.get("value_numeric"))
    if numeric is not None:
        return abs(numeric), abs(numeric)
    number = numeric_from_text(raw)
    return (number, number) if number is not None else (None, None)


def metric_text(kind: str, number: float | None, raw: str) -> str:
    if number is None:
        return "-"
    if kind == "today_new_station_bonus":
        return f"+{number:g}%"
    if kind == "memory_access_time":
        return raw or f"{number:g}"
    if kind == "radar_detection_range":
        return f"+{number:g}駅"
    if kind in {"station_link_transfer", "link_transfer"}:
        return f"{number:g}駅"
    return f"{number:g}回"


def level_value_text(level: str, value: dict[str, Any]) -> str:
    raw = base.clean_display_text(value.get("value_raw") or "-")
    return raw if level == base.DEFAULT_LEVEL else f"Lv{level}: {raw}"


def level_metrics(component: dict[str, Any], level: str) -> dict[str, Any] | None:
    values = component.get("values_by_denko_level") or {}
    value = values.get(level)
    if not value:
        return None
    kind = str(component.get("effect_kind") or "")
    raw = str(value.get("value_raw") or "")
    value_min, number = value_range(kind, value)
    average = base.mean_value(value_min, number)
    probability = probability_max(value)
    expected = average * probability / 100 if average is not None else None
    return {
        "level": level,
        "sort_max": number,
        "sort_avg": expected,
        "value_text": level_value_text(level, value),
        "max_text": metric_text(kind, number, raw),
        "avg_text": metric_text(kind, expected, raw) if expected is not None else "-",
        "probability": probability_text(value),
        "duration": value.get("duration") or "-",
        "cooldown": value.get("cooldown") or "-",
    }


def belongs_to_tab(tab_id: str, component: dict[str, Any]) -> bool:
    return component.get("effect_kind") in TABS[tab_id]["kinds"]


def candidate_search_text(parts: list[Any]) -> str:
    return " ".join(str(part or "") for part in parts).lower()


def build_candidates(tab_id: str, rows: list[dict[str, Any]], metadata: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    candidates = []
    for row in rows:
        denko_id = str(row.get("denko_id") or "")
        for component in row.get("skill_components") or []:
            if not belongs_to_tab(tab_id, component):
                continue
            levels = {
                level: metrics
                for level in base.REPORT_LEVELS
                if (metrics := level_metrics(component, level)) is not None
            }
            if not levels:
                continue
            fallback_level, _fallback_value = base.basis_value(component)
            if base.DEFAULT_LEVEL in levels:
                initial_level = base.DEFAULT_LEVEL
            elif fallback_level in levels:
                initial_level = fallback_level
            else:
                initial_level = next(iter(levels))
            initial = levels[initial_level]
            group_id, group_label = base.activation_group(row, component)
            denko_meta = metadata.get(denko_id, {})
            condition = base.display_condition_text(component)
            filters = base.compact_filter_text(component)
            target = base.target_text(component)
            kind = str(component.get("effect_kind") or "")
            level_data = json.dumps(levels, ensure_ascii=False, separators=(",", ":"))
            all_level_text = " ".join(str(metrics["value_text"]) for metrics in levels.values())
            search = candidate_search_text(
                [
                    denko_id,
                    row.get("name"),
                    denko_meta.get("attribute"),
                    denko_meta.get("type_key"),
                    component.get("component_id"),
                    kind,
                    condition,
                    target,
                    filters,
                    all_level_text,
                ]
            )
            candidates.append(
                {
                    "sort_max": initial["sort_max"],
                    "sort_avg": initial["sort_avg"],
                    "basis_level": initial_level,
                    "denko_id": denko_id,
                    "name": row.get("name"),
                    "attribute": denko_meta.get("attribute", "-"),
                    "type_key": denko_meta.get("type_key", "unknown"),
                    "kind": kind,
                    "component_id": component.get("component_id"),
                    "condition": condition,
                    "target": target,
                    "filters": filters,
                    "use_case": KIND_USE_CASE.get(kind, "-"),
                    "activation_group": group_id,
                    "activation_label": group_label,
                    "activation_type": component.get("activation_type") or row.get("activation_type") or "",
                    "probability": initial["probability"],
                    "duration": initial["duration"],
                    "cooldown": initial["cooldown"],
                    "level_value": initial["value_text"],
                    "max_text": initial["max_text"],
                    "avg_text": initial["avg_text"],
                    "level_data": level_data,
                    "vu_only": base.is_vu_only(component, fallback_level),
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
                    f'<td>{esc(EFFECT_LABELS.get(item["kind"], item["kind"]))}{component_html}</td>',
                    f'<td>{esc(item["use_case"])}</td>',
                    f'<td class="metric max-cell mobility-metric">{esc(item["max_text"])}</td>',
                    f'<td class="metric avg-cell mobility-metric">{esc(item["avg_text"])}</td>',
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
    panel_class = " tab-no-metrics" if tab_id == "extra_access" else ""
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
            <th>活动用途</th>
            <th class="mobility-metric">理论最大</th>
            <th class="mobility-metric">期望值</th>
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


def audit_candidates(candidates_by_tab: dict[str, list[dict[str, Any]]]) -> None:
    issues = []
    for tab_id, candidates in candidates_by_tab.items():
        for item in candidates:
            if item["kind"] not in NON_NUMERIC_ACCESS_KINDS:
                continue
            levels = json.loads(item["level_data"])
            if any(value["sort_max"] is not None or value["sort_avg"] is not None for value in levels.values()):
                issues.append(f"{tab_id}/{item['denko_id']}/{item['component_id']}: access behavior has numeric metric")

    expected_lv50 = {
        ("random_remote_access", "extra:001", "memory_access_station_count"): (5.0, 5.0),
        ("range_transfer", "original:047", "radar_detection_range"): (2.0, 2.0),
        ("new_station_bonus", "extra:104", "today_new_station_bonus"): (125.0, 125.0),
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
        raise ValueError("mobility metric audit failed: " + "; ".join(issues))


def main() -> None:
    rows = base.read_jsonl(SKILL_PATH)
    metadata = base.denko_metadata()
    candidates_by_tab = {tab_id: build_candidates(tab_id, rows, metadata) for tab_id in TABS}
    audit_candidates(candidates_by_tab)
    tab_buttons = "\n".join(
        f'<button class="tab-button" type="button" data-tab="{esc(tab_id)}">{esc(tab["title"])} {base.tab_count_html(candidates_by_tab[tab_id])}</button>'
        for tab_id, tab in TABS.items()
    )
    sections = "\n".join(render_table(tab_id, candidates_by_tab[tab_id]) for tab_id in TABS)
    counts = {tab_id: len(candidates) for tab_id, candidates in candidates_by_tab.items()}

    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Ekimemo Step2 位移/访问次数辅助</title>
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
    .toggle {{ display: inline-flex; align-items: center; gap: 5px; font-size: 13px; color: #444c56; }}
    .toggle input {{ padding: 0; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin-top: 12px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 7px 8px; vertical-align: top; }}
    th {{ background: #f6f8fa; position: sticky; top: 53px; z-index: 2; }}
    td:nth-child(10), td:nth-child(11), td:nth-child(12), td:nth-child(13) {{ white-space: nowrap; }}
    td:nth-child(15) {{ min-width: 280px; }}
    .metric {{ min-width: 96px; }}
    .tab-no-metrics .mobility-metric {{ display: none; }}
    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}
    a {{ color: #0969da; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <h1>Ekimemo Step2 位移/访问次数辅助</h1>
  <p>从 Step1 DB 自动整理。这个表面向“访问回数活动”“人在固定地点补访问”“长距离开图”场景；今日新駅奖励不是访问次数增加，已单独拆页签。</p>
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
  {base.interactive_script('extra_access')}
</body>
</html>
"""
    html_text = "\n".join(line.rstrip() for line in html_text.splitlines()) + "\n"
    base.write_text_lf(OUT_HTML, html_text)
    print(json.dumps({"out": str(OUT_HTML.relative_to(ROOT)), "counts": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
