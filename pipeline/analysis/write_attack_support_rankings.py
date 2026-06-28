from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DENKO_PATH = ROOT / "data" / "step1_db" / "denko_facts.jsonl"
SKILL_PATH = ROOT / "data" / "step1_db" / "skill_facts.jsonl"
OUT_HTML = ROOT / "data" / "reports" / "step2_attack_support_rankings_zh.html"


TABS = {
    "self_atk": {
        "title": "攻击手：自己加ATK",
        "description": "只看对自己生效的 ATK 增加。理论最大/平均值用 Lv50 AP 乘以 ATK 增幅估算。",
        "kinds": {"atk_buff"},
    },
    "team_atk": {
        "title": "ATK辅助：给队友/队伍",
        "description": "只看能给自身以外、队伍、访问者、相对车位等对象提供 ATK 增加的技能。",
        "kinds": {"atk_buff"},
    },
    "fixed_damage": {
        "title": "固定伤害",
        "description": "轻减不能/固定伤害。范围值同时给出理论最大和平均值。",
        "kinds": {"fixed_damage", "additional_fixed_damage"},
    },
    "def_debuff": {
        "title": "降低对手DEF",
        "description": "只看对手 DEF 下降。自降 DEF 或队友 DEF 下降不列入。",
        "kinds": {"def_debuff"},
    },
}

ACTIVATION_GROUPS = {
    "always": "常驻",
    "manual": "手动",
    "probability": "概率/自动",
}

EFFECT_LABELS = {
    "atk_buff": "ATK增加",
    "fixed_damage": "固定伤害",
    "additional_fixed_damage": "追加固定伤害",
    "def_debuff": "DEF下降",
}

SCOPE_LABELS = {
    "self": "自己",
    "team_all": "编成内全员",
    "opponent_denko": "对手でんこ",
    "own_front_car": "自己队伍先头",
    "opponent_front_car": "对手队伍先头",
    "accessing_denko": "访问中的でんこ",
    "accessed_denko": "被访问的でんこ",
    "relative_car": "相对车位",
}

LEVEL_PRIORITY = ["50", "92", "96", "100", "80", "70", "60", "30", "15", "5"]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def type_key(type_raw: str) -> str:
    if "\u30b5\u30dd" in type_raw:
        return "supporter"
    if "\u30a2\u30bf" in type_raw:
        return "attacker"
    if "\u30c7\u30a3" in type_raw:
        return "defender"
    if "\u30c8\u30ea" in type_raw:
        return "trickster"
    return "unknown"


def denko_metadata() -> dict[str, dict[str, str]]:
    metadata = {}
    for row in read_jsonl(DENKO_PATH):
        identity = row.get("identity") or {}
        denko_id = identity.get("denko_id") or row.get("denko_id")
        if denko_id:
            type_raw = str(identity.get("type") or "-")
            metadata[str(denko_id)] = {
                "attribute": str(identity.get("attribute") or "-"),
                "type_key": type_key(type_raw),
            }
    return metadata


def denko_sort_key(denko_id: str) -> tuple[int, int]:
    pool, _, number = denko_id.partition(":")
    return (0 if pool == "original" else 1, int(number or 0))


def is_vu_only(component: dict[str, Any], basis_level: str) -> bool:
    availability = component.get("availability") or {}
    if availability.get("vu_only") is True:
        return True
    return basis_level in {"92", "96", "100"}


def probability_text(value: dict[str, Any]) -> str:
    probability = value.get("probability")
    if not probability:
        return "-"
    if isinstance(probability, dict):
        parts = [f"{k} {v}" for k, v in probability.items() if v not in {None, "", "-"}]
        return " / ".join(parts) if parts else "-"
    return str(probability)


def probability_numbers(value: dict[str, Any]) -> list[float]:
    probability = value.get("probability")
    if not probability:
        return []
    text = json.dumps(probability, ensure_ascii=False) if isinstance(probability, dict) else str(probability)
    numbers = []
    for raw in re.findall(r"\d+(?:\.\d+)?\s*[％%]", text):
        match = re.search(r"\d+(?:\.\d+)?", raw)
        if match:
            numbers.append(float(match.group(0)))
    return numbers


def is_probability_trigger(component: dict[str, Any]) -> bool:
    for _level, value in all_level_values(component):
        nums = probability_numbers(value)
        if nums and any(number < 100 for number in nums):
            return True
    return False


def activation_group(row: dict[str, Any], component: dict[str, Any]) -> tuple[str, str]:
    activation_type = str(component.get("activation_type") or row.get("activation_type") or "")
    activation_mode = str((row.get("normalized_skill") or {}).get("activation_mode") or "")
    if is_probability_trigger(component) or activation_type == "でんこにおまかせ":
        return "probability", ACTIVATION_GROUPS["probability"]
    if activation_type == "マスターにおまかせ" or activation_mode == "passive_auto":
        return "manual", ACTIVATION_GROUPS["manual"]
    if activation_type == "いつでもアクティブ" or activation_mode == "always_active":
        return "always", ACTIVATION_GROUPS["always"]
    return "probability", "需确认"


def all_level_values(component: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    values = component.get("values_by_denko_level") or {}
    return sorted(values.items(), key=lambda item: int(item[0]) if str(item[0]).isdigit() else 999)


def basis_value(component: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    values = component.get("values_by_denko_level") or {}
    if is_vu_only(component, "50"):
        for level in ["100", "96", "92"]:
            if level in values:
                return level, values[level]
    for level in LEVEL_PRIORITY:
        if level in values:
            return level, values[level]
    return "-", {}


def as_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def signed_numbers(text: str) -> list[float]:
    nums = []
    for raw in re.findall(r"[+-]?\d+(?:\.\d+)?", text.replace("％", "%")):
        try:
            nums.append(float(raw))
        except ValueError:
            pass
    return nums


def formula_range_from_text(raw: str, condition: str) -> tuple[float | None, float | None]:
    distance_match = re.search(r"\+(\d+(?:\.\d+)?)×移動距離\(km\)%", raw)
    if distance_match and ("100km" in condition or "上限100" in condition):
        rate = float(distance_match.group(1))
        return 0.0, rate * 100
    over_100_match = re.search(r"\+(\d+(?:\.\d+)?)×\(移動距離\(km\)-100\)%", raw)
    if over_100_match:
        rate = float(over_100_match.group(1))
        return 0.0, rate * (360 - 100)
    return None, None


def value_range(tab_id: str, component: dict[str, Any], value: dict[str, Any]) -> tuple[float | None, float | None]:
    raw = str(value.get("value_raw") or "")
    condition = str(component.get("condition_raw") or "")
    numeric = as_number(value.get("value_numeric"))
    value_min = as_number(value.get("value_min"))
    value_max = as_number(value.get("value_max"))

    if tab_id == "def_debuff":
        nums = [abs(number) for number in signed_numbers(raw) if number < 0]
        if "～" in raw and nums:
            return min(nums), max(nums)
        if value_min is not None and value_max is not None:
            return min(abs(value_min), abs(value_max)), max(abs(value_min), abs(value_max))
        if numeric is not None:
            return abs(numeric), abs(numeric)
        return (max(nums), max(nums)) if nums else (None, None)

    if value_min is not None and value_max is not None and value_max >= value_min:
        return abs(value_min), abs(value_max)
    if value_max is not None and value_max >= 0:
        return 0.0 if "～" in raw else abs(value_max), abs(value_max)
    if numeric is not None:
        return abs(numeric), abs(numeric)

    formula_min, formula_max = formula_range_from_text(raw, condition)
    if formula_max is not None:
        return formula_min, formula_max

    nums = [abs(number) for number in signed_numbers(raw)]
    if "～" in raw and nums:
        return min(nums), max(nums)
    if nums:
        return max(nums), max(nums)
    return None, None


def mean_value(value_min: float | None, value_max: float | None) -> float | None:
    if value_min is None or value_max is None:
        return None
    return (value_min + value_max) / 2


def ap_at_level(row: dict[str, Any], level: str) -> float | None:
    stats = row.get("key_level_stats") or {}
    value = stats.get(level) or {}
    ap = value.get("AP")
    if ap not in {None, ""}:
        try:
            return float(ap)
        except ValueError:
            return None
    return None


def metric_display(tab_id: str, row: dict[str, Any], max_value: float | None, avg_value: float | None) -> tuple[str, str, float | None, float | None]:
    if tab_id != "self_atk":
        return format_metric(max_value), format_metric(avg_value), max_value, avg_value
    ap = ap_at_level(row, "50")
    if ap is None:
        return "-", "-", None, None
    max_result = ap * (1 + max_value / 100) if max_value is not None else None
    avg_result = ap * (1 + avg_value / 100) if avg_value is not None else None
    max_text = f"AP {max_result:g} / ATK +{max_value:g}%" if max_result is not None and max_value is not None else "-"
    avg_text = f"AP {avg_result:g} / ATK +{avg_value:g}%" if avg_result is not None and avg_value is not None else "-"
    return max_text, avg_text, max_result, avg_result


def format_metric(value: float | None) -> str:
    return "-" if value is None else f"{value:g}"


def lv50_text(component: dict[str, Any], basis_level: str, value: dict[str, Any]) -> str:
    if not value:
        return "-"
    raw = str(value.get("value_raw") or "-")
    if basis_level != "50":
        return f"※Lv{basis_level}: {raw}"
    return raw


def target_text(component: dict[str, Any]) -> str:
    scope = component.get("target_scope") or []
    if not scope:
        return "对象未明"
    return "、".join(SCOPE_LABELS.get(str(item), str(item)) for item in scope)


def compact_filter_text(component: dict[str, Any]) -> str:
    filters = component.get("target_filters") or {}
    trigger = component.get("trigger_conditions") or {}
    scaling = component.get("scaling_conditions") or {}
    notes = []
    if trigger.get("access_direction") == "active":
        notes.append("主动访问")
    elif trigger.get("access_direction") == "passive":
        notes.append("被访问")
    if trigger.get("event_hint") == "link":
        notes.append("link时")
    if filters.get("own_team_all_attribute"):
        notes.append(f"队伍全{filters['own_team_all_attribute']}")
    if filters.get("attribute"):
        notes.append(f"{filters['attribute']}对象")
    if filters.get("state") == "cooldown":
        notes.append("クールダウン中")
    if filters.get("attributes"):
        notes.append("对象属性 " + "/".join(map(str, filters["attributes"])))
    if filters.get("exclude_self"):
        notes.append("不含自己")
    if filters.get("type"):
        notes.append(f"对象类型 {filters['type']}")
    if scaling.get("basis"):
        notes.append(f"按{scaling['basis']}")
    return "；".join(notes) if notes else "-"


def is_self_only_atk(component: dict[str, Any]) -> bool:
    if component.get("effect_kind") != "atk_buff":
        return False
    scope = set(component.get("target_scope") or [])
    condition = str(component.get("condition_raw") or "")
    if scope == {"self"}:
        return True
    if "自身のATK" in condition and "編成内" not in condition:
        return True
    return False


def is_opponent_def_debuff(component: dict[str, Any]) -> bool:
    scope = set(component.get("target_scope") or [])
    condition = str(component.get("condition_raw") or "")
    if "opponent_denko" in scope:
        return True
    return bool(re.search(r"相手(?:のでんこ|でんこ)?のDEF|相手でんこのDEF", condition))


def belongs_to_tab(tab_id: str, component: dict[str, Any]) -> bool:
    if component.get("effect_kind") not in TABS[tab_id]["kinds"]:
        return False
    if tab_id == "self_atk":
        return is_self_only_atk(component)
    if tab_id == "team_atk":
        return not is_self_only_atk(component)
    if tab_id == "def_debuff":
        return is_opponent_def_debuff(component)
    return True


def build_candidates(tab_id: str, rows: list[dict[str, Any]], metadata: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    candidates = []
    for row in rows:
        for component in row.get("skill_components") or []:
            if not belongs_to_tab(tab_id, component):
                continue
            basis_level, value = basis_value(component)
            value_min, value_max = value_range(tab_id, component, value)
            avg_value = mean_value(value_min, value_max)
            max_text, avg_text, sort_max, sort_avg = metric_display(tab_id, row, value_max, avg_value)
            group_id, group_label = activation_group(row, component)
            denko_id = str(row.get("denko_id") or "")
            denko_meta = metadata.get(denko_id, {})
            target = "对手でんこ" if tab_id == "def_debuff" else target_text(component)
            filters = compact_filter_text(component)
            condition = str(component.get("condition_raw") or "")
            lv50 = lv50_text(component, basis_level, value)
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
                    lv50,
                ]
            ).lower()
            candidates.append(
                {
                    "sort_max": sort_max,
                    "sort_avg": sort_avg,
                    "basis_level": basis_level,
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
                    "probability": probability_text(value),
                    "duration": value.get("duration") or "-",
                    "cooldown": value.get("cooldown") or "-",
                    "lv50": lv50,
                    "max_text": max_text,
                    "avg_text": avg_text,
                    "vu_only": is_vu_only(component, basis_level),
                    "url": row.get("detail_url") or "",
                    "search": search,
                }
            )
    candidates.sort(
        key=lambda item: (
            -(item["sort_max"] if item["sort_max"] is not None else -1),
            denko_sort_key(str(item["denko_id"])),
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
                    f'<tr data-tab="{esc(tab_id)}" data-search="{esc(item["search"])}" data-activation="{esc(item["activation_group"])}" data-attr="{esc(item["attribute"])}" data-type="{esc(item["type_key"])}" data-vu-only="{str(item["vu_only"]).lower()}" data-sort-max="{item["sort_max"] if item["sort_max"] is not None else -1}" data-sort-avg="{item["sort_avg"] if item["sort_avg"] is not None else -1}">',
                    f'<td class="rank">{rank}</td>',
                    f'<td><strong>{esc(item["denko_id"])}</strong><br><a href="{esc(item["url"])}">{esc(item["name"])}</a></td>',
                    f'<td>{esc(item["attribute"])}</td>',
                    f'<td>{esc(item["type_key"])}</td>',
                    f'<td>{esc(EFFECT_LABELS.get(item["kind"], item["kind"]))}<br><span class="muted">{esc(item["component_id"])}</span></td>',
                    f'<td class="metric">{esc(item["max_text"])}</td>',
                    f'<td class="metric">{esc(item["avg_text"])}</td>',
                    f'<td>{esc(item["lv50"])}</td>',
                    f'<td>{esc(item["probability"])}</td>',
                    f'<td>{esc(item["duration"])}</td>',
                    f'<td>{esc(item["cooldown"])}</td>',
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
            <th>Lv50</th>
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
    rows = read_jsonl(SKILL_PATH)
    metadata = denko_metadata()
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
  <title>Ekimemo Step2 攻击辅助排行</title>
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
  <h1>Ekimemo Step2 攻击辅助排行</h1>
  <p>从 Step1 DB 自动整理。Lv50 作为默认查看基准；仅 VU 后生效的项目默认隐藏。范围型效果同时给出理论最大和平均值，并可切换排序。</p>
  <div class="tabs">{tab_buttons}</div>
  <div class="toolbar">
    <input id="q" placeholder="搜索ID、名字、条件、效果" size="34">
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
    const state = {{ activeTab: 'self_atk' }};
    const q = document.getElementById('q');
    const sortMode = document.getElementById('sortMode');
    const activation = document.getElementById('activation');
    const attr = document.getElementById('attr');
    const type = document.getElementById('type');
    const showVu = document.getElementById('showVu');
    const tabButtons = [...document.querySelectorAll('.tab-button')];
    const panels = [...document.querySelectorAll('[data-tab-panel]')];
    const rowCache = new Map();

    for (const panel of panels) {{
      rowCache.set(panel.dataset.tabPanel, [...panel.querySelectorAll('tbody tr')]);
    }}

    function activeRows() {{
      return rowCache.get(state.activeTab) || [];
    }}

    function sortActiveRows() {{
      const rows = activeRows();
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
        const visible = okText && okActivation && okAttr && okType && okVu;
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
    for (const input of [q, sortMode, activation, attr, type, showVu]) {{
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
