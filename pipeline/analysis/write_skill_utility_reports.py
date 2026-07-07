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


TABS = {
    "interference": {
        "title": "技能干扰/无效化",
        "description": "技能无效化、属性技能封锁、伤害无效、保命、反向惩罚等不适合混进普通攻防倍率的技能。",
    },
    "cooldown_probability": {
        "title": "CD/概率操作",
        "description": "改变技能发动率、冷却时间、效果时间、再次发动概率的技能。用于搭配主动技能和概率技能。",
    },
    "condition_index": {
        "title": "条件索引",
        "description": "按天气、气温、星期、时间、属性、类型、film、link、车序等限制整理，方便判断配队是否能满足条件。",
    },
    "event_access": {
        "title": "活动/访问次数",
        "description": "访问次数、随机访问、传送/额外访问、新駅/今日の新駅、路线开图和活动回数相关技能。",
    },
}

EFFECT_LABELS = {
    **base.EFFECT_LABELS,
    "skill_disable": "技能无效化",
    "damage_nullification": "伤害无效化",
    "hp_zero": "HP归零/リブート",
    "reboot": "リブート相关",
    "extra_access": "额外访问",
    "random_access": "随机访问",
    "range_transfer": "传送/范围访问",
    "today_new_station_bonus": "今日の新駅ボーナス",
    "link_bonus": "linkボーナス",
    "mile_gain": "mile付与",
    "effect_multiplier": "效果量强化",
    "activation_probability_boost": "发动率强化",
    "duration_extension": "效果时间延长",
    "unknown": "未分类效果",
}

CONDITION_PATTERNS = [
    ("气温", r"気温|温度|℃|30度|15度|10度"),
    ("天气", r"天気|晴|雨|雪|曇"),
    ("星期", r"曜日|月曜日|火曜日|水曜日|木曜日|金曜日|土曜日|日曜日"),
    ("时间", r"時間帯|午前|午後|昼|夜|\d{1,2}:\d{2}|\d{1,2}時(?:から|まで|以降|以前)"),
    ("属性", r"cool|heat|eco|属性"),
    ("类型", r"attacker|defender|supporter|trickster|タイプ"),
    ("film", r"フィルム|ラッピング|テーマ"),
    ("车序", r"先頭|前|後ろ|編成内.*番目|車両"),
    ("link", r"リンク時間|リンク駅数|最大リンク|保持|駅数"),
    ("站点/路线", r"今日の新駅|新駅|駅数|駅名|路線名|アクセスしたことのある駅"),
    ("对手条件", r"相手|相手でんこ|相手の編成"),
]


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def compact(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def row_text(row: dict[str, Any], component: dict[str, Any], *, include_source_text: bool) -> str:
    chunks: list[str] = [
        str(row.get("effect_summary") or ""),
        str(row.get("trigger_condition") or ""),
        str(component.get("condition_raw") or ""),
        str(component.get("remarks_raw") or ""),
        json.dumps(component.get("target_filters") or {}, ensure_ascii=False),
        json.dumps(component.get("scaling_conditions") or {}, ensure_ascii=False),
        json.dumps(component.get("trigger_conditions") or {}, ensure_ascii=False),
    ]
    for value in (component.get("values_by_denko_level") or {}).values():
        chunks.append(str(value.get("value_raw") or ""))
        if include_source_text:
            chunks.append(str(value.get("source_text") or ""))
    return compact(" ".join(chunks))


def condition_tags(text: str, component: dict[str, Any]) -> list[str]:
    tags = [label for label, pattern in CONDITION_PATTERNS if re.search(pattern, text, re.I)]
    if component.get("target_filters"):
        tags.append("对象/编成限制")
    if component.get("scaling_conditions"):
        tags.append("随条件变化")
    out: list[str] = []
    for tag in tags:
        if tag not in out:
            out.append(tag)
    return out


def is_interference(text: str, component: dict[str, Any]) -> bool:
    kind = str(component.get("effect_kind") or "")
    tags = set(component.get("modeling_tags") or [])
    return (
        kind in {"skill_disable", "damage_nullification", "hp_zero", "reboot"}
        or "attribute_skill_nullification" in tags
        or "offensive_skill_interference" in tags
        or "partial_damage_increase_skill_nullification" in tags
        or bool(re.search(r"無効化|無効|発動しません|発動しない|リブートしそう|HPが0|フットバ", text))
    )


def is_cooldown_probability(text: str, component: dict[str, Any]) -> bool:
    meaningful = (
        r"クールタイム.*(短縮|減少|延長|増加)|"
        r"(発動率|確率).*(UP|アップ|増加|上昇|減少|追加|リセット)|"
        r"(効果時間|発動時間).*(延長|短縮|増加|減少)|"
        r"次回の発動率|スキル効果時間"
    )
    return bool(re.search(meaningful, text, re.I)) or bool((component.get("scaling_conditions") or {}).get("probability_scaling"))


def is_event_access(text: str, component: dict[str, Any]) -> bool:
    kind = str(component.get("effect_kind") or "")
    tags = set(component.get("modeling_tags") or [])
    return (
        kind in {"extra_access", "random_access", "range_transfer", "today_new_station_bonus", "link_bonus", "mile_gain"}
        or bool(tags & {"soft_station_sustained_scoring", "visit_count_event_helper"})
        or bool(re.search(r"アクセス回数|ランダム|アクセスしたことのある駅|今日の新駅|新駅|駅にアクセス|移動|おでかけ|回数", text))
    )


def level_brief(component: dict[str, Any]) -> str:
    values = component.get("values_by_denko_level") or {}
    parts = []
    for level in ("30", "50", "80", "92", "100"):
        value = values.get(level)
        if value:
            raw = base.clean_display_text(value.get("value_raw") or value.get("effect") or "")
            if raw:
                parts.append(f"Lv{level}: {raw}")
    return " / ".join(parts) or "-"


def display_target(component: dict[str, Any]) -> str:
    target = base.target_text(component)
    target = re.sub(r"component:[\w_]+", "关联效果", target)
    target = re.sub(r"(关联效果)(?:、关联效果)+", r"\1", target)
    return target


def make_item(tab_id: str, row: dict[str, Any], component: dict[str, Any], metadata: dict[str, dict[str, str]]) -> dict[str, Any] | None:
    semantic_text = row_text(row, component, include_source_text=False)
    search_text = row_text(row, component, include_source_text=True)
    tags = condition_tags(semantic_text, component)
    if tab_id == "interference" and not is_interference(semantic_text, component):
        return None
    if tab_id == "cooldown_probability" and not is_cooldown_probability(semantic_text, component):
        return None
    if tab_id == "condition_index" and not tags:
        return None
    if tab_id == "event_access" and not is_event_access(semantic_text, component):
        return None

    denko_id = str(row.get("denko_id") or "")
    denko_meta = metadata.get(denko_id, {})
    group_id, group_label = base.activation_group(row, component)
    condition = base.display_condition_text(component)
    filters = base.compact_filter_text(component)
    target = display_target(component)
    kind = str(component.get("effect_kind") or "unknown")
    return {
        "denko_id": denko_id,
        "name": row.get("name") or "",
        "url": row.get("detail_url") or "",
        "attribute": denko_meta.get("attribute", "-"),
        "type_key": denko_meta.get("type_key", "unknown"),
        "kind": kind,
        "effect": EFFECT_LABELS.get(kind, kind),
        "activation_group": group_id,
        "activation_label": group_label,
        "activation_type": component.get("activation_type") or row.get("activation_type") or "",
        "target": target,
        "filters": filters,
        "condition": condition,
        "tags": tags,
        "level_brief": level_brief(component),
        "search": " ".join([denko_id, str(row.get("name") or ""), denko_meta.get("attribute", ""), denko_meta.get("type_key", ""), kind, search_text, " ".join(tags)]).lower(),
    }


def build_items(tab_id: str, rows: list[dict[str, Any]], metadata: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        for component in row.get("skill_components") or []:
            item = make_item(tab_id, row, component, metadata)
            if not item:
                continue
            key = (item["denko_id"], str(component.get("component_id") or ""), tab_id)
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
    items.sort(key=lambda item: (base.denko_sort_key(item["denko_id"]), item["effect"], item["condition"]))
    return items


def render_rows(items: list[dict[str, Any]]) -> str:
    out = []
    for index, item in enumerate(items, 1):
        url = f'<a href="{esc(item["url"])}">{esc(item["name"])}</a>' if item["url"] else esc(item["name"])
        tag_html = " ".join(f'<span class="chip">{esc(tag)}</span>' for tag in item["tags"]) or '<span class="muted">-</span>'
        out.append(
            "".join(
                [
                    f'<tr data-search="{esc(item["search"])}" data-activation="{esc(item["activation_group"])}" data-attr="{esc(item["attribute"])}" data-type="{esc(item["type_key"])}">',
                    f'<td class="rank">{index}</td>',
                    f'<td><strong>{esc(item["denko_id"])}</strong><br>{url}</td>',
                    f'<td>{esc(item["attribute"])}</td>',
                    f'<td>{esc(item["type_key"])}</td>',
                    f'<td>{esc(item["effect"])}</td>',
                    f'<td title="{esc(item["activation_type"])}">{esc(item["activation_label"])}</td>',
                    f'<td>{esc(item["target"])}<br><span class="muted">{esc(item["filters"])}</span></td>',
                    f'<td>{tag_html}</td>',
                    f'<td>{esc(item["level_brief"])}</td>',
                    f'<td>{esc(item["condition"])}</td>',
                    "</tr>",
                ]
            )
        )
    return "".join(out)


def render_table(tab_id: str, items: list[dict[str, Any]]) -> str:
    tab = TABS[tab_id]
    active = " active" if tab_id == next(iter(TABS)) else ""
    return f"""
    <section class="tab-panel{active}" id="panel-{esc(tab_id)}" data-tab-panel="{esc(tab_id)}">
      <h2>{esc(tab["title"])} <span class="count-main">{len(items)}</span></h2>
      <p>{esc(tab["description"])}</p>
      <table>
        <thead>
          <tr>
            <th>排行</th><th>でんこ</th><th>属性</th><th>类型</th><th>效果</th><th>发动</th><th>对象/限制</th><th>条件标签</th><th>关键等级值</th><th>触发与条件</th>
          </tr>
        </thead>
        <tbody>{render_rows(items)}</tbody>
      </table>
    </section>
    """


def main() -> None:
    rows = base.read_jsonl(SKILL_PATH)
    metadata = base.denko_metadata()
    items_by_tab = {tab_id: build_items(tab_id, rows, metadata) for tab_id in TABS}
    visible_tabs = [tab_id for tab_id in TABS if items_by_tab[tab_id]]
    default_tab = visible_tabs[0] if visible_tabs else next(iter(TABS))
    buttons = "\n".join(
        f'<button class="tab-button{" active" if tab_id == default_tab else ""}" type="button" data-tab="{esc(tab_id)}">{esc(TABS[tab_id]["title"])} <span class="count-main">{len(items_by_tab[tab_id])}</span></button>'
        for tab_id in visible_tabs
    )
    sections = "\n".join(render_table(tab_id, items_by_tab[tab_id]) for tab_id in visible_tabs)
    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Ekimemo Step2 技能工具索引</title>
  <style>
    body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; margin: 24px; color: #1f2328; line-height: 1.45; }}
    h1 {{ margin-bottom: 6px; }}
    h2 {{ margin-top: 24px; border-bottom: 1px solid #d8dee4; padding-bottom: 6px; }}
    .tabs {{ display: flex; gap: 6px; flex-wrap: wrap; margin: 12px 0; }}
    .toolbar {{ position: sticky; top: 0; z-index: 3; background: white; border-bottom: 1px solid #d8dee4; padding: 12px 0; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
    button, input, select {{ padding: 7px 9px; border: 1px solid #c9d1d9; border-radius: 4px; font-size: 14px; background: white; }}
    button {{ cursor: pointer; }}
    .tab-button.active {{ background: #0969da; color: white; border-color: #0969da; }}
    .muted {{ color: #68707c; font-size: 12px; }}
    .chip {{ display: inline-block; margin: 1px 4px 1px 0; padding: 1px 6px; border: 1px solid #d0d7de; border-radius: 999px; background: #f6f8fa; font-size: 12px; white-space: nowrap; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin-top: 12px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 7px 8px; vertical-align: top; }}
    th {{ background: #f6f8fa; position: sticky; top: 53px; z-index: 2; }}
    td:nth-child(10) {{ min-width: 280px; }}
    .tab-panel {{ display: none; }}
    .tab-panel.active {{ display: block; }}
    a {{ color: #0969da; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <h1>Ekimemo Step2 技能工具索引</h1>
  <p>从 Step1 DB 自动整理。这个页面不做收益排行，专门承接配队时需要查的机制型技能：干扰、CD/概率、复杂条件、活动访问。</p>
  <div class="tabs">{buttons}</div>
  <div class="toolbar">
    <input id="q" placeholder="搜索ID、名字、条件、效果" size="34">
    <select id="activation">
      <option value="">全部发动</option>
      <option value="always">常驻</option>
      <option value="manual">手动</option>
      <option value="non_probability">非概率触发</option>
      <option value="probability">概率/自动</option>
    </select>
    <select id="attr"><option value="">全部属性</option><option value="cool">cool</option><option value="heat">heat</option><option value="eco">eco</option></select>
    <select id="type"><option value="">全部类型</option><option value="attacker">attacker</option><option value="defender">defender</option><option value="supporter">supporter</option><option value="trickster">trickster</option></select>
  </div>
  {sections}
  <script>
    const q = document.querySelector('#q');
    const activation = document.querySelector('#activation');
    const attr = document.querySelector('#attr');
    const type = document.querySelector('#type');
    const buttons = Array.from(document.querySelectorAll('.tab-button'));
    const panels = Array.from(document.querySelectorAll('[data-tab-panel]'));
    let activeTab = '{esc(default_tab)}';
    function rows() {{ return Array.from(document.querySelectorAll(`#panel-${{activeTab}} tbody tr`)); }}
    function applyFilter() {{
      const needle = q.value.trim().toLowerCase();
      let rank = 1;
      for (const row of rows()) {{
        const okText = !needle || row.dataset.search.includes(needle);
        const okActivation = !activation.value || row.dataset.activation === activation.value || (activation.value === 'non_probability' && ['always', 'manual'].includes(row.dataset.activation));
        const okAttr = !attr.value || row.dataset.attr === attr.value;
        const okType = !type.value || row.dataset.type === type.value;
        const visible = okText && okActivation && okAttr && okType;
        row.style.display = visible ? '' : 'none';
        if (visible) row.querySelector('.rank').textContent = rank++;
      }}
    }}
    function setActive(tab) {{
      activeTab = tab;
      buttons.forEach(button => button.classList.toggle('active', button.dataset.tab === tab));
      panels.forEach(panel => panel.classList.toggle('active', panel.dataset.tabPanel === tab));
      applyFilter();
    }}
    buttons.forEach(button => button.addEventListener('click', () => setActive(button.dataset.tab)));
    [q, activation, attr, type].forEach(control => control.addEventListener('input', applyFilter));
    applyFilter();
  </script>
</body>
</html>
"""
    html_text = "\n".join(line.rstrip() for line in html_text.splitlines()) + "\n"
    base.write_text_lf(OUT_HTML, html_text)
    print(json.dumps({"out": str(OUT_HTML.relative_to(ROOT)), "counts": {tab_id: len(items) for tab_id, items in items_by_tab.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
