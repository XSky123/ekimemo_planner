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
OUT_HTML = ROOT / "data" / "reports" / "step2_defense_support_rankings_zh.html"

TABS = {
    "self_def": {
        "title": "守站本体：自己DEF",
        "description": "只看主要保护自己的 DEF 增加。适合找单体守站核心。",
        "kinds": {"def_buff"},
        "default_score": None,
    },
    "team_def": {
        "title": "DEF辅助：队友/队伍",
        "description": "给自身以外、队伍、被访问者或特定对象提供 DEF 的候选。",
        "kinds": {"def_buff"},
        "default_score": None,
    },
    "damage_reduction": {
        "title": "伤害减轻/上限",
        "description": "固定减伤、百分比减伤、伤害上限等。无法用单一数值表达时保留为条件型候选。",
        "kinds": {"damage_reduction", "damage_cap"},
        "default_score": None,
    },
    "defense_effect_boost": {
        "title": "防御效果量倍率",
        "description": "提高 DEF 增加、固定减伤、伤害减轻类技能效果量的候选。用于叠防御辅助时估算放大器。",
        "kinds": {"effect_multiplier"},
        "default_score": None,
    },
    "hp_recovery": {
        "title": "HP回复/续航",
        "description": "HP回复、被访问后回复、手动回复等。平均值按数值和范围估算，不直接模拟战斗。",
        "kinds": {"hp_recovery", "hp_recovery_bonus"},
        "default_score": None,
    },
    "nullify_survival": {
        "title": "无效化/保命",
        "description": "伤害无效化、HP1保命、代受伤害等。排序以触发可靠性和等级值可读性为主。",
        "kinds": {"damage_nullification", "survive_hp1", "damage_substitution"},
        "default_score": 100.0,
    },
    "opponent_suppression": {
        "title": "降低对手输出",
        "description": "降低对手 ATK、技能无效化、电池无效化等。这里只列防御向干扰，不列降低对手 DEF。",
        "kinds": {"atk_debuff", "skill_disable", "battery_disable"},
        "default_score": 100.0,
    },
    "link_retention": {
        "title": "link保持",
        "description": "HP归零后仍保持其他 link、link继续等。适合守多站或远征保站场景。",
        "kinds": {"link_continue", "link_retention"},
        "default_score": 100.0,
    },
    "counter_disruption": {
        "title": "反击/惩罚",
        "description": "カウンター、反击伤害、重启对手、强制 HP 0。严格说不是防御，但能提高被打时收益或威慑。",
        "kinds": {"counter", "counter_damage", "reboot", "force_hp_zero"},
        "default_score": 100.0,
    },
}
RELIABILITY_TABS = {"nullify_survival", "link_retention", "counter_disruption"}

EFFECT_LABELS = {
    "atk_debuff": "对手ATK降低",
    "battery_disable": "电池无效化",
    "counter": "カウンター",
    "counter_damage": "反击伤害",
    "damage_cap": "伤害上限",
    "damage_nullification": "伤害无效化",
    "damage_reduction": "伤害减轻",
    "damage_substitution": "代受伤害",
    "def_buff": "DEF增加",
    "effect_multiplier": "防御效果量增加",
    "force_hp_zero": "强制HP0",
    "hp_recovery": "HP回复",
    "hp_recovery_bonus": "HP回复追加",
    "link_continue": "link继续",
    "link_retention": "link保持",
    "reboot": "リブート",
    "skill_disable": "技能无效化",
    "survive_hp1": "HP1保命",
}

base.SCOPE_LABELS.update(
    {
        "front_car": "先头车",
        "component:hp_recovery_1": "指定技能分量",
    }
)


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def is_self_only_def(component: dict[str, Any]) -> bool:
    scope = set(component.get("target_scope") or [])
    condition = str(component.get("condition_raw") or "")
    if scope == {"self"}:
        return True
    return "自身のDEF" in condition and "編成内" not in condition


def is_opponent_output_suppression(component: dict[str, Any]) -> bool:
    kind = component.get("effect_kind")
    if kind in {"skill_disable", "battery_disable"}:
        return True
    if kind != "atk_debuff":
        return False
    scope = set(component.get("target_scope") or [])
    condition = str(component.get("condition_raw") or "")
    return "opponent_denko" in scope or bool(re.search(r"相手(?:のでんこ|でんこ)?のATK|相手でんこのATK", condition))


def is_defense_effect_multiplier(component: dict[str, Any]) -> bool:
    text = " ".join(
        str(component.get(key) or "")
        for key in ("condition_raw", "remarks_raw", "component_id")
    )
    return any(
        marker in text
        for marker in (
            "DEF",
            "ダメージを固定値で軽減",
            "ダメージ軽減",
            "軽減するスキル",
        )
    )


def belongs_to_tab(tab_id: str, component: dict[str, Any]) -> bool:
    kind = component.get("effect_kind")
    if kind not in TABS[tab_id]["kinds"]:
        return False
    if tab_id == "self_def":
        return is_self_only_def(component)
    if tab_id == "team_def":
        return not is_self_only_def(component)
    if tab_id == "opponent_suppression":
        return is_opponent_output_suppression(component)
    if tab_id == "defense_effect_boost":
        return is_defense_effect_multiplier(component)
    return True


def max_unit_count(component: dict[str, Any]) -> float:
    for container_key in ("target_filters", "scaling_conditions"):
        container = component.get(container_key) or {}
        for key in (
            "max_station_count",
            "max_count",
            "max_linked_station_count",
            "max_units",
            "max_n",
        ):
            number = base.as_number(container.get(key))
            if number is not None:
                return number

    context = " ".join(
        str(item or "")
        for item in (
            component.get("condition_raw"),
            component.get("remarks_raw"),
            component.get("condition_label"),
        )
    )
    match = re.search(r"(?:上限|最大)\s*(\d+(?:\.\d+)?)\s*(?:駅|体|人|両|個)?", context)
    if match:
        return float(match.group(1))
    return 7.0


def metric_range(tab_id: str, component: dict[str, Any], value: dict[str, Any]) -> tuple[float | None, float | None]:
    raw = str(value.get("value_raw") or "")
    numeric = base.as_number(value.get("value_numeric"))
    value_min = base.as_number(value.get("value_min"))
    value_max = base.as_number(value.get("value_max"))
    formula_match = re.search(r"\+?\s*(\d+(?:\.\d+)?)\s*[×xX]\s*n\s*駅?\s*%", raw, flags=re.IGNORECASE)
    if formula_match:
        return 0.0, float(formula_match.group(1)) * max_unit_count(component)
    reverse_formula_match = re.search(r"\+?\s*n\s*駅?\s*[×xX]\s*(\d+(?:\.\d+)?)\s*%", raw, flags=re.IGNORECASE)
    if reverse_formula_match:
        return 0.0, float(reverse_formula_match.group(1)) * max_unit_count(component)
    if value_min is not None and value_max is not None:
        return min(abs(value_min), abs(value_max)), max(abs(value_min), abs(value_max))
    if tab_id == "defense_effect_boost" and "倍" in raw and numeric is not None:
        return abs(numeric), abs(numeric)
    if numeric is not None:
        return abs(numeric), abs(numeric)

    numbers = base.signed_numbers(raw)
    if tab_id == "opponent_suppression":
        negatives = [abs(number) for number in numbers if number < 0]
        if negatives:
            return min(negatives), max(negatives)
    if numbers:
        positive = [abs(number) for number in numbers]
        if any(mark in raw for mark in ("～", "~", "〜")) and len(positive) >= 2:
            return min(positive), max(positive)
        return max(positive), max(positive)
    return None, None


def probability_factor(value: dict[str, Any]) -> float:
    nums = base.probability_numbers(value)
    if not nums:
        return 100.0
    return min(max(nums), 100.0)


def metric_text(value: float | None, fallback: str) -> str:
    if value is None:
        return fallback
    return f"{value:g}"


def level_value_text(level: str, value: dict[str, Any], kind: str) -> str:
    raw = str(value.get("value_raw") or "-")
    if raw in {"def_buff", "damage_reduction", "hp_recovery", "skill_disable", "battery_disable", "counter", "reboot", "damage_nullification"}:
        raw = "条件型"
    if kind in {"reboot", "force_hp_zero", "link_continue", "link_retention", "survive_hp1"} and (
        "スコア" in raw or "経験値" in raw or raw in {"link_continue", "force_hp_zero"}
    ):
        raw = "条件型"
    if level != base.DEFAULT_LEVEL:
        return f"※Lv{level}: {raw}"
    return raw


def level_metrics(tab_id: str, component: dict[str, Any], level: str) -> dict[str, Any] | None:
    values = component.get("values_by_denko_level") or {}
    value = values.get(level)
    if not value:
        return None
    if value.get("unit") == "report_ignore":
        return None

    kind = str(component.get("effect_kind") or "")
    value_min, value_max = metric_range(tab_id, component, value)
    default_score = TABS[tab_id]["default_score"]
    uses_reliability_score = False
    if (tab_id in RELIABILITY_TABS and kind != "counter_damage") or (value_max is None and default_score is not None):
        reliability = probability_factor(value)
        value_min = reliability
        value_max = reliability
        uses_reliability_score = True
    if value_max is None:
        return None
    avg = base.mean_value(value_min, value_max)
    expected = avg if uses_reliability_score else (avg * probability_factor(value) / 100 if avg is not None else None)
    max_text = f"{value_max:g}%" if uses_reliability_score and value_max is not None else metric_text(value_max, "条件型")
    avg_text = f"{expected:g}%" if uses_reliability_score and expected is not None else metric_text(expected, "条件型")
    return {
        "level": level,
        "sort_max": value_max,
        "sort_avg": expected,
        "value_text": level_value_text(level, value, kind),
        "max_text": max_text,
        "avg_text": avg_text,
        "probability": base.probability_text(value),
        "duration": value.get("duration") or "-",
        "cooldown": value.get("cooldown") or "-",
    }


def target_text(component: dict[str, Any]) -> str:
    scope = component.get("target_scope") or []
    if not scope:
        return "对象未明"
    return "、".join(base.SCOPE_LABELS.get(str(item), str(item)) for item in scope)


def defense_target_text(tab_id: str, component: dict[str, Any]) -> str:
    kind = component.get("effect_kind")
    if tab_id == "opponent_suppression":
        if kind == "atk_debuff":
            return "对手でんこ"
        if kind == "skill_disable":
            filters = component.get("target_filters") or {}
            if filters.get("disabled_skill_kind") == "attribute_skill_nullification":
                return "属性技能无效化"
            if filters.get("disabled_skill_kind") == "partial_damage_increase_skill_nullification":
                return "部分伤害增加技能无效化"
            return "对手技能"
        if kind == "battery_disable":
            return "对手/电池使用"
    return target_text(component)


def build_candidates(tab_id: str, rows: list[dict[str, Any]], metadata: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in rows:
        for component in row.get("skill_components") or []:
            if not belongs_to_tab(tab_id, component):
                continue
            levels = {
                level: metrics
                for level in base.REPORT_LEVELS
                if (metrics := level_metrics(tab_id, component, level)) is not None
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
            denko_id = str(row.get("denko_id") or "")
            denko_meta = metadata.get(denko_id, {})
            condition = base.display_condition_text(component)
            filters = base.compact_filter_text(component)
            target = defense_target_text(tab_id, component)
            level_data = json.dumps(levels, ensure_ascii=False, separators=(",", ":"))
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
  <title>Ekimemo Step2 防御/守站辅助排行</title>
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
  <h1>Ekimemo Step2 防御/守站辅助排行</h1>
  <p>从 Step1 DB 自动整理。防御候选按 DEF、减伤、回复、无效化/保命、降低对手输出、link保持、反击惩罚拆分；默认 Lv50，可切换 Lv30/Lv80/Lv92/Lv100。理论最大是该维度的原始量级，期望值会粗略乘以发动概率。</p>
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
      <option value="avg">按期望值排序</option>
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
    const state = {{ activeTab: 'self_def' }};
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
