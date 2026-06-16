from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DENKO_PATH = ROOT / "data" / "step1_db" / "denko_facts.jsonl"
SKILL_PATH = ROOT / "data" / "step1_db" / "skill_facts.jsonl"
OUT_HTML = ROOT / "data" / "reports" / "step1_human_overview_zh.html"


EFFECT_LABELS = {
    "atk_buff": "ATK增加",
    "def_buff": "DEF增加",
    "atk_debuff": "降低对手ATK",
    "def_debuff": "降低对手DEF",
    "def_modifier": "DEF变化",
    "hp_recovery": "HP回复",
    "fixed_damage": "固定伤害",
    "additional_fixed_damage": "追加固定伤害",
    "damage_reduction": "伤害减轻",
    "exp_gain": "经验值相关",
    "exp_distribution": "经验值分配",
    "score_gain": "得分增加",
    "additional_score_gain": "追加得分",
    "skill_disable": "技能无效化",
    "footbar": "フットバース",
    "cooldown_reduction": "缩短CD",
    "cooldown_reset": "重置CD",
    "cooldown_entry": "进入CD",
    "duration_extension": "延长技能时间",
    "activation_probability_boost": "提高发动率",
    "effect_multiplier": "提高技能效果量",
    "link_bonus": "link bonus增加",
    "link_bonus_zero": "link bonus归零",
    "counter": "カウンター",
    "reboot": "リブート",
    "force_hp_zero": "HP归零",
    "memory_access_station_count": "访问车站记忆",
    "memory_access_time": "访问时间记忆",
    "score_random_modifier": "随机得分变化",
}

SCOPE_LABELS = {
    "self": "自己",
    "team_all": "编成内全员",
    "opponent_denko": "对手でんこ",
    "own_front_car": "自己队伍先头",
    "opponent_front_car": "对手队伍先头",
}

TYPE_LABELS = {
    "attacker": "attacker",
    "defender": "defender",
    "supporter": "supporter",
    "trickster": "trickster",
    "アタッカー": "attacker",
    "ディフェンダー": "defender",
    "サポーター": "supporter",
    "トリックスター": "trickster",
}

ATTR_LABELS = {
    "heat": "heat",
    "cool": "cool",
    "eco": "eco",
    "flat": "flat",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def attr_label(value: Any) -> str:
    return ATTR_LABELS.get(str(value), str(value))


def effect_label(kind: Any) -> str:
    return EFFECT_LABELS.get(str(kind), str(kind))


def denko_sort_key(row: dict[str, Any]) -> tuple[int, int]:
    denko_id = row.get("denko_id") or row.get("identity", {}).get("denko_id") or ""
    pool, _, number = str(denko_id).partition(":")
    return (0 if pool == "original" else 1, int(number or 0))


def probability_text(probability: Any) -> str:
    if not probability:
        return ""
    if isinstance(probability, dict):
        parts = [f"{k} {v}" for k, v in probability.items() if v not in {None, "", "-"}]
        return " / ".join(parts)
    return str(probability)


def value_at(component: dict[str, Any], level: str) -> str:
    value = (component.get("values_by_denko_level") or {}).get(level) or {}
    parts = []
    if value.get("value_raw"):
        parts.append(str(value["value_raw"]))
    prob = probability_text(value.get("probability"))
    if prob:
        parts.append(prob)
    if value.get("duration"):
        parts.append(f"持续 {value['duration']}")
    if value.get("cooldown"):
        parts.append(f"CD {value['cooldown']}")
    if not parts:
        availability = component.get("availability") or {}
        levels = [str(item) for item in availability.get("levels") or []]
        if any(int(item) > int(level) for item in levels if item.isdigit()) and not any(
            int(item) <= int(level) for item in levels if item.isdigit()
        ):
            return "未解锁"
        return "-"
    return "，".join(parts)


def component_condition(component: dict[str, Any]) -> str:
    condition = str(component.get("condition_raw") or "").strip()
    filters = component.get("target_filters") or {}
    trigger = component.get("trigger_conditions") or {}
    notes: list[str] = []

    if trigger.get("access_direction") == "active":
        notes.append("主动访问时")
    elif trigger.get("access_direction") == "passive":
        notes.append("被访问时")
    elif trigger.get("access_directions"):
        notes.append("访问/被访问时")
    if trigger.get("event_hint") == "link":
        notes.append("link时")
    if trigger.get("hp_threshold_percent"):
        notes.append(f"HP {trigger['hp_threshold_percent']}%以下")
    if filters.get("own_team_all_attribute"):
        notes.append(f"队伍全{attr_label(filters['own_team_all_attribute'])}")
    if filters.get("opponent_attribute"):
        notes.append(f"对手{attr_label(filters['opponent_attribute'])}")
    if filters.get("attribute"):
        notes.append(f"{attr_label(filters['attribute'])}对象")
    if filters.get("attributes"):
        notes.append("对象属性：" + "/".join(attr_label(item) for item in filters["attributes"]))
    if filters.get("type"):
        notes.append(f"对象类型：{TYPE_LABELS.get(filters['type'], filters['type'])}")
    if filters.get("opponent_type"):
        notes.append(f"对手类型：{TYPE_LABELS.get(filters['opponent_type'], filters['opponent_type'])}")
    if filters.get("exclude_self"):
        notes.append("不含自己")
    if filters.get("state") == "cooldown":
        notes.append("对象在CD中")
    count_filter = filters.get("opponent_team_attribute_count") or {}
    if count_filter:
        basis = "自己+对手队伍" if count_filter.get("includes_own_team") else "对手队伍"
        cap = f"，上限{count_filter['max_count']}体" if count_filter.get("max_count") else ""
        notes.append(f"按{basis}{attr_label(count_filter.get('attribute'))}数量{cap}")

    suffix = f"（{'; '.join(notes)}）" if notes else ""
    return (condition or "条件未明") + suffix


def target_text(component: dict[str, Any]) -> str:
    scope = component.get("target_scope") or []
    if not scope:
        return "对象未明"
    labels = []
    for item in scope:
        item = str(item)
        if item.startswith("component:"):
            labels.append("作用于另一技能")
        else:
            labels.append(SCOPE_LABELS.get(item, item))
    return "、".join(labels)


def component_line(component: dict[str, Any]) -> str:
    label = component.get("condition_label") or ""
    kind = effect_label(component.get("effect_kind"))
    target = target_text(component)
    condition = component_condition(component)
    return f"{label} {kind}｜对象：{target}｜条件：{condition}".strip()


def stat_pair(stats: dict[str, Any], level: str) -> str:
    value = stats.get(level) or {}
    hp = value.get("HP") or "-"
    ap = value.get("AP") or "-"
    return f"Lv{level} AP {ap} / HP {hp}"


def practical_tags(components: list[dict[str, Any]]) -> list[str]:
    kinds = {component.get("effect_kind") for component in components}
    tags = []
    if kinds & {"atk_buff", "fixed_damage", "additional_fixed_damage", "def_debuff", "footbar"}:
        tags.append("进攻")
    if kinds & {"def_buff", "damage_reduction", "hp_recovery", "counter"}:
        tags.append("防守/保站")
    if kinds & {"exp_gain", "exp_distribution", "score_gain", "additional_score_gain", "effect_multiplier"}:
        tags.append("收益")
    if kinds & {"cooldown_reduction", "cooldown_reset", "duration_extension", "activation_probability_boost"}:
        tags.append("技能辅助")
    if kinds & {"skill_disable", "link_bonus_zero", "force_hp_zero", "reboot"}:
        tags.append("特殊干扰")
    return tags or ["其他"]


def main() -> None:
    denko_rows = read_jsonl(DENKO_PATH)
    skill_rows = {row["denko_id"]: row for row in read_jsonl(SKILL_PATH)}
    merged = []
    for denko in denko_rows:
        identity = denko.get("identity") or {}
        denko_id = identity.get("denko_id") or denko.get("denko_id")
        skill = skill_rows.get(denko_id, {})
        merged.append((identity, skill))
    merged.sort(key=lambda pair: denko_sort_key({"denko_id": pair[0].get("denko_id")}))

    rows_html = []
    for identity, skill in merged:
        components = skill.get("skill_components") or []
        stats = skill.get("key_level_stats") or {}
        denko_id = identity.get("denko_id")
        pool = identity.get("id_pool") or identity.get("pool")
        name = identity.get("full_name") or identity.get("name")
        attr = identity.get("attribute") or "-"
        type_name = identity.get("type") or "-"
        color = identity.get("color") or "-"
        tags = practical_tags(components)
        component_lines = "".join(f"<li>{esc(component_line(component))}</li>" for component in components)
        lv30 = "<br>".join(esc(f"{effect_label(c.get('effect_kind'))}: {value_at(c, '30')}") for c in components) or "-"
        lv50 = "<br>".join(esc(f"{effect_label(c.get('effect_kind'))}: {value_at(c, '50')}") for c in components) or "-"
        vu_levels = sorted(
            {
                level
                for component in components
                for level in ((component.get("availability") or {}).get("levels") or [])
                if str(level).isdigit() and int(level) >= 92
            },
            key=lambda item: int(item),
        )
        vu = "有 VU/Lv92+要素：" + "/".join(vu_levels) if vu_levels else "无明显 VU 段"
        detail_url = identity.get("detail_url") or skill.get("detail_url") or ""
        rows_html.append(
            "\n".join(
                [
                    f'<tr data-pool="{esc(pool)}" data-attr="{esc(attr)}" data-tags="{esc(" ".join(tags))}">',
                    f"<td><strong>{esc(denko_id)}</strong><br>{esc(pool)}</td>",
                    f'<td><a href="{esc(detail_url)}">{esc(name)}</a><br><span class="muted">{esc(color)} / {esc(attr)} / {esc(type_name)}</span></td>',
                    f"<td>{esc('、'.join(tags))}</td>",
                    f"<td><ul>{component_lines}</ul></td>",
                    f"<td>{lv30}</td>",
                    f"<td>{lv50}</td>",
                    f"<td>{esc(stat_pair(stats, '30'))}<br>{esc(stat_pair(stats, '50'))}<br>{esc(stat_pair(stats, '80'))}</td>",
                    f"<td>{esc(vu)}</td>",
                    "</tr>",
                ]
            )
        )

    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Ekimemo Step1 人工查阅总览表</title>
  <style>
    body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; margin: 24px; color: #1f2328; line-height: 1.45; }}
    h1 {{ margin-bottom: 4px; font-size: 26px; }}
    .muted {{ color: #68707c; font-size: 12px; }}
    .toolbar {{ position: sticky; top: 0; z-index: 2; background: white; border-bottom: 1px solid #d8dee4; padding: 12px 0; display: flex; gap: 8px; flex-wrap: wrap; align-items: center; }}
    input, select {{ padding: 7px 9px; border: 1px solid #c9d1d9; border-radius: 4px; font-size: 14px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 14px; font-size: 13px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 8px; vertical-align: top; }}
    th {{ background: #f6f8fa; position: sticky; top: 54px; z-index: 1; }}
    td:nth-child(4) {{ min-width: 360px; }}
    ul {{ margin: 0; padding-left: 18px; }}
    li {{ margin-bottom: 6px; }}
    a {{ color: #0969da; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .summary {{ margin: 10px 0 14px; color: #4b5563; }}
  </style>
</head>
<body>
  <h1>Ekimemo Step1 人工查阅总览表</h1>
  <p class="summary">一行一个でんこ。重点看：这个角色大概干什么、触发条件、Lv30/Lv50 实用值、AP/HP 关键节点。原文事实仍保留日语，说明文字尽量用中文。</p>
  <div class="toolbar">
    <input id="q" placeholder="搜索ID、名字、技能、条件" size="34">
    <select id="pool">
      <option value="">全部系列</option>
      <option value="original">original</option>
      <option value="extra">extra</option>
    </select>
    <select id="attr">
      <option value="">全部属性</option>
      <option value="heat">heat</option>
      <option value="cool">cool</option>
      <option value="eco">eco</option>
      <option value="flat">flat</option>
    </select>
    <select id="tag">
      <option value="">全部用途</option>
      <option value="进攻">进攻</option>
      <option value="防守/保站">防守/保站</option>
      <option value="收益">收益</option>
      <option value="技能辅助">技能辅助</option>
      <option value="特殊干扰">特殊干扰</option>
    </select>
    <span class="muted" id="count"></span>
  </div>
  <table id="overview">
    <thead>
      <tr>
        <th>ID</th>
        <th>でんこ</th>
        <th>用途</th>
        <th>技能怎么理解</th>
        <th>Lv30 重点</th>
        <th>Lv50 重点</th>
        <th>AP/HP</th>
        <th>VU提示</th>
      </tr>
    </thead>
    <tbody>
{''.join(rows_html)}
    </tbody>
  </table>
  <script>
    const q = document.getElementById('q');
    const pool = document.getElementById('pool');
    const attr = document.getElementById('attr');
    const tag = document.getElementById('tag');
    const count = document.getElementById('count');
    const rows = [...document.querySelectorAll('#overview tbody tr')];
    function applyFilter() {{
      const needle = q.value.trim().toLowerCase();
      let shown = 0;
      for (const row of rows) {{
        const okText = !needle || row.innerText.toLowerCase().includes(needle);
        const okPool = !pool.value || row.dataset.pool === pool.value;
        const okAttr = !attr.value || row.dataset.attr === attr.value;
        const okTag = !tag.value || row.dataset.tags.includes(tag.value);
        const visible = okText && okPool && okAttr && okTag;
        row.style.display = visible ? '' : 'none';
        if (visible) shown++;
      }}
      count.textContent = `显示 ${{shown}} / ${{rows.length}}`;
    }}
    [q, pool, attr, tag].forEach(el => el.addEventListener('input', applyFilter));
    applyFilter();
  </script>
</body>
</html>
"""
    OUT_HTML.write_text(html_text, encoding="utf-8")
    print(json.dumps({"out": str(OUT_HTML.relative_to(ROOT)), "rows": len(merged)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
