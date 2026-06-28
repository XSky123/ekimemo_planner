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
OUT_HTML = ROOT / "data" / "reports" / "step2_exp_pt_support_rankings_zh.html"


TABS = {
    "exp_gain": {
        "title": "经验获取",
        "description": "经验值付与/增加类。对象可能是自己、访问中的でんこ、队伍、或相手でんこ，具体看对象列。",
        "kinds": {"exp_gain"},
    },
    "exp_distribution": {
        "title": "经验分配",
        "description": "把自身或相手获得的经验分配给其他でんこ的技能。",
        "kinds": {"exp_distribution", "exp_distribution_bonus"},
    },
    "score_gain": {
        "title": "スコア/PT获取",
        "description": "スコア獲得、スコア増加、随机スコア增减、追加スコア獲得等收益类技能。",
        "kinds": {"score_gain", "additional_score_gain", "score_random_modifier"},
    },
    "bonus_gain": {
        "title": "ボーナス/マイル",
        "description": "リンクボーナス、今日の新駅ボーナス、マイル付与等偏 PT/通勤收益的技能。",
        "kinds": {"link_bonus", "today_new_station_bonus", "mile_gain"},
    },
    "effect_boost": {
        "title": "经验/PT效果强化",
        "description": "经验、スコア、リンクボーナス、相关アクセサリー等收益技能的効果量増加。",
        "kinds": {"effect_multiplier"},
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


def belongs_to_tab(tab_id: str, component: dict[str, Any]) -> bool:
    kind = component.get("effect_kind")
    if kind not in TABS[tab_id]["kinds"]:
        return False
    if tab_id == "effect_boost":
        return is_positive_effect_multiplier(component)
    return True


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


def value_range(component: dict[str, Any], value: dict[str, Any]) -> tuple[float | None, float | None]:
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


def metric_text(kind: str, value: float | None) -> str:
    if value is None:
        return "-"
    if kind == "effect_multiplier":
        return f"{value:g}倍"
    return f"{value:g}"


def level_value_text(level: str, value: dict[str, Any]) -> str:
    raw = str(value.get("value_raw") or "-")
    return raw if level == DEFAULT_LEVEL else f"※Lv{level}: {raw}"


def level_metrics(component: dict[str, Any], level: str) -> dict[str, Any] | None:
    values = component.get("values_by_denko_level") or {}
    value = values.get(level)
    if not value:
        return None
    value_min, value_max = value_range(component, value)
    avg_value = mean_value(value_min, value_max)
    kind = str(component.get("effect_kind") or "")
    return {
        "level": level,
        "sort_max": value_max,
        "sort_avg": avg_value,
        "value_text": level_value_text(level, value),
        "max_text": metric_text(kind, value_max),
        "avg_text": metric_text(kind, avg_value),
        "probability": base.probability_text(value),
        "duration": value.get("duration") or "-",
        "cooldown": value.get("cooldown") or "-",
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


def build_candidates(tab_id: str, rows: list[dict[str, Any]], metadata: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    candidates = []
    for row in rows:
        for component in row.get("skill_components") or []:
            if not belongs_to_tab(tab_id, component):
                continue
            levels = {
                level: metrics
                for level in REPORT_LEVELS
                if (metrics := level_metrics(component, level)) is not None
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
            denko_id = str(row.get("denko_id") or "")
            denko_meta = metadata.get(denko_id, {})
            target = target_text(component)
            filters = base.compact_filter_text(component)
            condition = str(component.get("condition_raw") or "")
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
        rows.append(
            "\n".join(
                [
                    f'<tr data-tab="{esc(tab_id)}" data-search="{esc(item["search"])}" data-activation="{esc(item["activation_group"])}" data-attr="{esc(item["attribute"])}" data-type="{esc(item["type_key"])}" data-vu-only="{str(item["vu_only"]).lower()}" data-sort-max="{item["sort_max"] if item["sort_max"] is not None else -1}" data-sort-avg="{item["sort_avg"] if item["sort_avg"] is not None else -1}" data-levels="{esc(item["level_data"])}">',
                    f'<td class="rank">{rank}</td>',
                    f'<td><strong>{esc(item["denko_id"])}</strong><br><a href="{esc(item["url"])}">{esc(item["name"])}</a></td>',
                    f'<td>{esc(item["attribute"])}</td>',
                    f'<td>{esc(item["type_key"])}</td>',
                    f'<td>{esc(EFFECT_LABELS.get(str(item["kind"]), item["kind"]))}<br><span class="muted">{esc(item["component_id"])}</span></td>',
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
            <th>理论最大</th>
            <th>平均值</th>
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
  <p>从 Step1 DB 自动整理，分类参考 wiki「経験値、スコア系スキル」。默认按 Lv50 查看，可切换 Lv30/Lv80/Lv92/Lv100；仅 VU 后生效的项目默认隐藏。</p>
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
    const state = {{ activeTab: 'exp_gain' }};
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
