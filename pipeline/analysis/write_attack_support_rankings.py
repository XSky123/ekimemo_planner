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


CATEGORIES = {
    "atk_percent": {
        "title": "ATK百分比增加",
        "description": "看谁能给主攻或自己提供 ATK +%。默认按 Lv50 的最大百分比排序。",
        "kinds": {"atk_buff"},
        "score_label": "ATK增加",
    },
    "fixed_damage": {
        "title": "固定伤害",
        "description": "看谁能追加轻减不能/固定伤害。范围值按上限排序，例如 1～210 记作 210。",
        "kinds": {"fixed_damage", "additional_fixed_damage"},
        "score_label": "固定伤害",
    },
    "def_debuff": {
        "title": "降低对手DEF",
        "description": "只看能让对手 DEF 下降的技能。排序用下降幅度，例如 DEF -35% 记作 35%。自降DEF、队友降DEF不列入这个维度。",
        "kinds": {"def_debuff"},
        "score_label": "DEF下降",
    },
}

ACTIVATION_GROUPS = [
    ("always", "常驻技能", "基本不需要按技能按钮；适合作为稳定底盘。"),
    ("manual", "手动触发技能", "需要开技能，重点看持续时间和CD。"),
    ("probability", "概率/自动触发技能", "发动不完全稳定，重点看概率、触发条件和是否能接受波动。"),
]


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
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def denko_attributes() -> dict[str, str]:
    attrs = {}
    for row in read_jsonl(DENKO_PATH):
        identity = row.get("identity") or {}
        denko_id = identity.get("denko_id") or row.get("denko_id")
        if denko_id:
            attrs[str(denko_id)] = str(identity.get("attribute") or "-")
    return attrs


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def denko_sort_key(denko_id: str) -> tuple[int, int]:
    pool, _, number = denko_id.partition(":")
    return (0 if pool == "original" else 1, int(number or 0))


def probability_text(value: dict[str, Any]) -> str:
    probability = value.get("probability")
    if not probability:
        return ""
    if isinstance(probability, dict):
        return " / ".join(f"{k} {v}" for k, v in probability.items() if v not in {None, "", "-"})
    return str(probability)


def probability_numbers(value: dict[str, Any]) -> list[float]:
    probability = value.get("probability")
    if not probability:
        return []
    text = json.dumps(probability, ensure_ascii=False) if isinstance(probability, dict) else str(probability)
    numbers = []
    for raw in re.findall(r"\d+(?:\.\d+)?\s*[％%]", text):
        try:
            numbers.append(float(re.search(r"\d+(?:\.\d+)?", raw).group(0)))
        except (AttributeError, ValueError):
            pass
    return numbers


def is_probability_trigger(component: dict[str, Any]) -> bool:
    values = component.get("values_by_denko_level") or {}
    for level in ("50", "30"):
        nums = probability_numbers(values.get(level) or {})
        if nums and any(number < 100 for number in nums):
            return True
    for _, value in all_level_values(component):
        nums = probability_numbers(value)
        if nums and any(number < 100 for number in nums):
            return True
    return False


def activation_group(row: dict[str, Any], component: dict[str, Any]) -> tuple[str, str]:
    activation_type = str(component.get("activation_type") or row.get("activation_type") or "")
    activation_mode = str((row.get("normalized_skill") or {}).get("activation_mode") or "")
    if is_probability_trigger(component) or activation_type == "でんこにおまかせ":
        return "probability", "概率/自动触发"
    if activation_type == "マスターにおまかせ" or activation_mode == "passive_auto":
        return "manual", "手动触发"
    if activation_type == "いつでもアクティブ" or activation_mode == "always_active":
        return "always", "常驻"
    return "probability", "发动方式需确认"


def value_text(component: dict[str, Any], level: str) -> str:
    value = (component.get("values_by_denko_level") or {}).get(level) or {}
    parts = []
    if value.get("value_raw"):
        parts.append(str(value["value_raw"]))
    prob = probability_text(value)
    if prob:
        parts.append(prob)
    if value.get("duration"):
        parts.append(f"持续 {value['duration']}")
    if value.get("cooldown"):
        parts.append(f"CD {value['cooldown']}")
    return "，".join(parts) if parts else "-"


def all_level_values(component: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    values = component.get("values_by_denko_level") or {}
    return sorted(values.items(), key=lambda item: int(item[0]) if str(item[0]).isdigit() else 999)


def signed_numbers(text: str) -> list[float]:
    nums = []
    for raw in re.findall(r"[+-]?\d+(?:\.\d+)?", text.replace("％", "%")):
        try:
            nums.append(float(raw))
        except ValueError:
            pass
    return nums


def score_for_value(category: str, value: dict[str, Any]) -> float | None:
    raw = str(value.get("value_raw") or "")
    if not raw:
        return None
    if category == "def_debuff":
        negatives = [number for number in signed_numbers(raw) if number < 0]
        if negatives:
            return max(abs(number) for number in negatives)
        numeric = value.get("value_numeric")
        if isinstance(numeric, (int, float)) and numeric < 0:
            return abs(float(numeric))
        return None
    if category == "fixed_damage":
        for key in ("value_max", "value_numeric"):
            numeric = value.get(key)
            if isinstance(numeric, (int, float)):
                return abs(float(numeric))
        nums = signed_numbers(raw)
        return max(abs(number) for number in nums) if nums else None
    numeric_candidates = []
    for key in ("value_max", "value_numeric"):
        numeric = value.get(key)
        if isinstance(numeric, (int, float)):
            numeric_candidates.append(float(numeric))
    if numeric_candidates:
        return max(abs(number) for number in numeric_candidates)
    nums = signed_numbers(raw)
    return max(abs(number) for number in nums) if nums else None


def primary_score(category: str, component: dict[str, Any]) -> tuple[float | None, str]:
    values = component.get("values_by_denko_level") or {}
    for level in ("50", "30"):
        score = score_for_value(category, values.get(level) or {})
        if score is not None:
            return score, f"Lv{level}"
    for level, value in all_level_values(component):
        score = score_for_value(category, value)
        if score is not None:
            return score, f"Lv{level}"
    return None, "-"


def target_text(component: dict[str, Any]) -> str:
    scope = component.get("target_scope") or []
    if not scope:
        return "对象未明"
    labels = []
    for item in scope:
        item = str(item)
        labels.append(SCOPE_LABELS.get(item, item))
    return "、".join(labels)


def compact_filter_text(component: dict[str, Any]) -> str:
    filters = component.get("target_filters") or {}
    trigger = component.get("trigger_conditions") or {}
    notes = []
    if trigger.get("access_direction") == "active":
        notes.append("主动访问")
    elif trigger.get("access_direction") == "passive":
        notes.append("被访问")
    if trigger.get("event_hint") == "link":
        notes.append("link时")
    if filters.get("own_team_all_attribute"):
        notes.append(f"队伍全{filters['own_team_all_attribute']}")
    if filters.get("opponent_attribute"):
        notes.append(f"对手{filters['opponent_attribute']}")
    if filters.get("attribute"):
        notes.append(f"{filters['attribute']}对象")
    if filters.get("attributes"):
        notes.append("对象属性 " + "/".join(map(str, filters["attributes"])))
    if filters.get("exclude_self"):
        notes.append("不含自己")
    if filters.get("type"):
        notes.append(f"对象类型 {filters['type']}")
    count_filter = filters.get("opponent_team_attribute_count") or {}
    if count_filter:
        basis = "自己+对手队伍" if count_filter.get("includes_own_team") else "对手队伍"
        max_count = f"上限{count_filter['max_count']}体" if count_filter.get("max_count") else ""
        notes.append(f"按{basis}{count_filter.get('attribute')}数量{max_count}")
    return "；".join(notes) if notes else "-"


def support_judgement(component: dict[str, Any]) -> str:
    scope = set(component.get("target_scope") or [])
    condition = str(component.get("condition_raw") or "")
    filters = component.get("target_filters") or {}
    if "team_all" in scope or filters.get("exclude_self"):
        return "可辅助主攻"
    if "編成内" in condition and "自身の" not in condition:
        return "可辅助主攻"
    if scope == {"self"}:
        return "偏自用"
    if "opponent_denko" in scope:
        return "看触发者"
    return "需人工判断"


def row_note(component: dict[str, Any]) -> str:
    availability = component.get("availability") or {}
    levels = [str(level) for level in availability.get("levels") or []]
    notes = []
    if availability.get("vu_only") or any(level.isdigit() and int(level) >= 92 for level in levels):
        notes.append("含VU/Lv92+")
    reasons = component.get("review_reasons") or []
    if reasons:
        notes.append("需复查：" + ",".join(map(str, reasons[:2])))
    return "；".join(notes) if notes else "-"


def is_opponent_def_debuff(component: dict[str, Any]) -> bool:
    scope = set(component.get("target_scope") or [])
    condition = str(component.get("condition_raw") or "")
    if "opponent_denko" in scope:
        return True
    return bool(re.search(r"相手(?:のでんこ|でんこ)?のDEF|相手でんこのDEF", condition))


def build_candidates(category: str, rows: list[dict[str, Any]], attrs: dict[str, str]) -> list[dict[str, Any]]:
    wanted = CATEGORIES[category]["kinds"]
    candidates = []
    for row in rows:
        for component in row.get("skill_components") or []:
            if component.get("effect_kind") not in wanted:
                continue
            if category == "def_debuff" and not is_opponent_def_debuff(component):
                continue
            score, basis = primary_score(category, component)
            support = support_judgement(component)
            group_id, group_label = activation_group(row, component)
            denko_id = str(row.get("denko_id") or "")
            target = "对手でんこ" if category == "def_debuff" else target_text(component)
            candidates.append(
                {
                    "score": score,
                    "basis": basis,
                    "denko_id": denko_id,
                    "name": row.get("name"),
                    "attribute": attrs.get(denko_id, "-"),
                    "pool": row.get("pool"),
                    "kind": component.get("effect_kind"),
                    "component_id": component.get("component_id"),
                    "condition": component.get("condition_raw") or "",
                    "target": target,
                    "filters": compact_filter_text(component),
                    "support": support,
                    "activation_group": group_id,
                    "activation_label": group_label,
                    "activation_type": component.get("activation_type") or row.get("activation_type") or "",
                    "lv30": value_text(component, "30"),
                    "lv50": value_text(component, "50"),
                    "url": row.get("detail_url") or "",
                }
            )
    support_order = {"可辅助主攻": 0, "看触发者": 1, "需人工判断": 2, "偏自用": 3}
    candidates.sort(
        key=lambda item: (
            support_order.get(str(item["support"]), 2),
            0 if item["basis"] == "Lv50" else 1 if item["basis"] == "Lv30" else 2,
            -(item["score"] if item["score"] is not None else -1),
            denko_sort_key(str(item["denko_id"])),
            str(item["component_id"]),
        )
    )
    return candidates


def render_table(category: str, candidates: list[dict[str, Any]]) -> str:
    title = CATEGORIES[category]["title"]
    score_label = CATEGORIES[category]["score_label"]
    grouped_html = []
    for group_id, group_title, group_description in ACTIVATION_GROUPS:
        group_items = [item for item in candidates if item["activation_group"] == group_id]
        body = []
        for rank, item in enumerate(group_items, 1):
            score = "-" if item["score"] is None else f"{item['score']:g}"
            body.append(
                "\n".join(
                    [
                        f'<tr data-support="{esc(item["support"])}" data-activation="{esc(item["activation_group"])}">',
                        f"<td>{rank}</td>",
                        f"<td><strong>{esc(item['denko_id'])}</strong><br><a href=\"{esc(item['url'])}\">{esc(item['name'])}</a></td>",
                        f"<td>{esc(item['attribute'])}</td>",
                        f"<td>{esc(EFFECT_LABELS.get(item['kind'], item['kind']))}<br><span class=\"muted\">{esc(item['component_id'])}</span></td>",
                        f"<td><strong>{esc(score)}</strong><br><span class=\"muted\">{esc(item['basis'])}</span></td>",
                        f"<td>{esc(item['activation_label'])}<br><span class=\"muted\">{esc(item['activation_type'])}</span></td>",
                        f"<td>{esc(item['support'])}</td>",
                        f"<td>{esc(item['target'])}<br><span class=\"muted\">{esc(item['filters'])}</span></td>",
                        f"<td>{esc(item['condition'])}</td>",
                        f"<td>{esc(item['lv30'])}</td>",
                        f"<td>{esc(item['lv50'])}</td>",
                        "</tr>",
                    ]
                )
            )
        grouped_html.append(
            f"""
      <h3>{esc(group_title)} <span class="muted">({len(group_items)})</span></h3>
      <p class="muted">{esc(group_description)}</p>
      <table>
        <thead>
          <tr>
            <th>排行</th>
            <th>でんこ</th>
            <th>属性</th>
            <th>效果</th>
            <th>{esc(score_label)}</th>
            <th>发动方式</th>
            <th>辅助判断</th>
            <th>对象/限制</th>
            <th>触发与条件</th>
            <th>Lv30</th>
            <th>Lv50</th>
          </tr>
        </thead>
        <tbody>{''.join(body)}</tbody>
      </table>
            """
        )
    return f"""
    <section id="{esc(category)}">
      <h2>{esc(title)}</h2>
      <p>{esc(CATEGORIES[category]["description"])}</p>
      {''.join(grouped_html)}
    </section>
    """


def main() -> None:
    rows = read_jsonl(SKILL_PATH)
    attrs = denko_attributes()
    sections = []
    counts = {}
    for category in CATEGORIES:
        candidates = build_candidates(category, rows, attrs)
        counts[category] = len(candidates)
        sections.append(render_table(category, candidates))

    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>Ekimemo Step2 攻击辅助排行</title>
  <style>
    body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; margin: 24px; color: #1f2328; line-height: 1.45; }}
    h1 {{ margin-bottom: 6px; }}
    h2 {{ margin-top: 30px; border-bottom: 1px solid #d8dee4; padding-bottom: 6px; }}
    .muted {{ color: #68707c; font-size: 12px; }}
    .toolbar {{ position: sticky; top: 0; z-index: 2; background: white; border-bottom: 1px solid #d8dee4; padding: 12px 0; display: flex; gap: 8px; flex-wrap: wrap; }}
    input, select {{ padding: 7px 9px; border: 1px solid #c9d1d9; border-radius: 4px; font-size: 14px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; margin-top: 12px; }}
    th, td {{ border: 1px solid #d8dee4; padding: 7px 8px; vertical-align: top; }}
    th {{ background: #f6f8fa; position: sticky; top: 53px; z-index: 1; }}
    td:nth-child(7) {{ min-width: 300px; }}
    a {{ color: #0969da; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <h1>Ekimemo Step2 攻击辅助排行</h1>
  <p>从 Step1 DB 自动整理。三类分别看 ATK百分比、固定伤害、降低对手DEF。每类再拆成常驻、手动触发、概率/自动触发。排序先看“可辅助主攻”，再按 Lv50 实用值，其次 Lv30、VU/其他等级。偏自用技能仍保留在表内，方便比较主攻自身能力。</p>
  <div class="toolbar">
    <input id="q" placeholder="搜索ID、名字、条件、效果" size="36">
    <select id="support">
      <option value="">全部</option>
      <option value="可辅助主攻">只看可辅助主攻</option>
      <option value="偏自用">只看偏自用</option>
      <option value="看触发者">只看触发者</option>
    </select>
    <select id="activation">
      <option value="">全部发动方式</option>
      <option value="always">常驻技能</option>
      <option value="manual">手动触发技能</option>
      <option value="probability">概率/自动触发技能</option>
    </select>
    <span class="muted">ATK {counts['atk_percent']} / 固定伤害 {counts['fixed_damage']} / DEF下降 {counts['def_debuff']}</span>
  </div>
  {''.join(sections)}
  <script>
    const q = document.getElementById('q');
    const support = document.getElementById('support');
    const activation = document.getElementById('activation');
    const rows = [...document.querySelectorAll('tbody tr')];
    function applyFilter() {{
      const needle = q.value.trim().toLowerCase();
      for (const row of rows) {{
        const okText = !needle || row.innerText.toLowerCase().includes(needle);
        const okSupport = !support.value || row.dataset.support === support.value;
        const okActivation = !activation.value || row.dataset.activation === activation.value;
        row.style.display = okText && okSupport && okActivation ? '' : 'none';
      }}
    }}
    q.addEventListener('input', applyFilter);
    support.addEventListener('input', applyFilter);
    activation.addEventListener('input', applyFilter);
  </script>
</body>
</html>
"""
    html_text = "\n".join(line.rstrip() for line in html_text.splitlines()) + "\n"
    OUT_HTML.write_text(html_text, encoding="utf-8")
    print(json.dumps({"out": str(OUT_HTML.relative_to(ROOT)), "counts": counts}, ensure_ascii=False))


if __name__ == "__main__":
    main()
