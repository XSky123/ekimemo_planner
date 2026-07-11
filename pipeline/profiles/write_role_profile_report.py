from __future__ import annotations

import html
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROFILES = ROOT / "data" / "role_profiles" / "role_profiles.jsonl"
MANIFEST = ROOT / "data" / "role_profiles" / "manifest.json"
PRIOR_AUDIT = ROOT / "data" / "audits" / "recommendation_prior_audit.json"
OUT = ROOT / "data" / "reports" / "step3_role_profile_scenarios_zh.html"

SCENES = [
    ("capture", "突破/抢站", "直接提高攻击、固定伤害或降低对手防御。"),
    ("defense", "守站", "提高 DEF、减伤、回复、生存或 link 保持。"),
    ("commute", "通勤低操作", "不依赖频繁手动操作的自动或常驻型贡献。"),
    ("expedition", "远征/连续 link", "额外访问、远程/随机访问、站点转移、探测与连续 link。"),
    ("visit_count_event", "回数活动", "能直接创造、延展或替代一次访问机会的机制。"),
    ("score_exp", "积分/经验", "影响积分、经验、里程、今日新站或物品收益。"),
    ("growth", "成长", "经验获取或分配相关能力。"),
    ("mechanism", "机制与干扰", "无效化、技能效果操作等必须结合队伍上下文的组件。"),
]

EFFECT_ZH = {
    "atk_buff": "ATK增加", "ap_buff": "AP增加", "fixed_damage": "固定伤害", "additional_fixed_damage": "追加固定伤害",
    "def_debuff": "降低对手DEF", "atk_debuff": "降低ATK", "def_buff": "DEF增加", "damage_reduction": "伤害轻减",
    "hp_recovery": "HP回复", "hp_recovery_bonus": "回复强化", "survive_hp1": "保留1HP", "damage_nullification": "伤害无效化",
    "damage_cap": "伤害上限", "damage_substitution": "伤害替代", "link_continue": "link持续", "link_retention": "link保持",
    "counter": "反击", "counter_damage": "反击伤害", "reboot": "reboot", "exp_gain": "经验获取", "exp_distribution": "经验分配",
    "exp_distribution_bonus": "经验分配强化", "score_gain": "积分获取", "additional_score_gain": "追加积分", "score_random_modifier": "积分随机变动",
    "match_bonus": "匹配奖励", "mile_gain": "里程获取", "today_new_station_bonus": "今日新站奖励", "item_gain": "道具获取",
    "extra_access": "追加访问", "random_previous_station_access": "随机已访问站访问", "remote_station_access": "远程访问",
    "station_link_transfer": "站点 link 转移", "link_transfer": "link转移", "radar_detection_range": "雷达范围", "radar_max_detection_range": "雷达最大范围",
    "memory_access_station_count": "思い出し访问站数", "memory_access_time": "思い出し访问时间", "skill_disable": "技能无效化",
    "skill_effect_nullification": "技能效果无效化", "skill_force_end": "强制结束技能", "battery_disable": "禁止电池",
    "footbar": "footbar", "force_hp_zero": "HP归零", "activation_probability_boost": "技能发动率操作",
    "cooldown_reduction": "CD缩短", "cooldown_reset": "CD重置", "cooldown_entry": "进入CD", "duration_extension": "效果时间延长",
    "effect_multiplier": "效果量强化", "film_effect_multiplier": "film效果强化", "film_series_effect_boost": "film系列效果强化",
    "friend_slot_increase": "电友槽增加", "skill_continue": "技能持续", "link_bonus": "link bonus", "link_bonus_zero": "link bonus归零",
    "def_modifier": "DEF修正", "ap_debuff": "AP降低", "none": "无可用效果",
}
SCOPE_ZH = {
    "self": "自己", "team_all": "编成内全员", "own_team": "己方编成", "opponent_team": "对手编成", "opponent_denko": "对手でんこ",
    "accessing_denko": "访问中的でんこ", "accessed_denko": "被访问的でんこ", "front_car": "先头车", "own_front_car": "己方先头",
    "opponent_front_car": "对手先头", "relative_car": "相对车位", "own_skill_effects": "自身技能效果", "master": "Master",
}
COST_ZH = {
    "manual_activation": "需要手动发动", "probabilistic": "概率发动", "long_cooldown": "CD较长", "vu_dependency": "VU后才可用",
    "context_or_formation_constraint": "有场景/编成限制", "self_debuff": "带自损/副作用",
}
CONSTRAINT_ZH = {
    "attribute": "属性对象限制", "attributes": "属性对象限制", "own_team_all_attribute": "统一属性编成", "type": "类型限制",
    "formation_only": "编成限制", "position_relative_to_self": "车位限制", "relative_position": "车位限制", "opponent_type": "对手类型限制",
    "opponent_attribute": "对手属性限制", "weather": "天气", "temperature_band": "气温", "time_window": "时间段",
    "season_months": "季节/月", "weekday": "星期", "hp_threshold_percent": "HP阈值", "linked_station_min_count": "link站数",
    "own_team_attribute_set": "编成属性组合", "opponent_pool_in": "对手系列", "opponent_pool_excludes": "对手系列",
    "own_skill_conflict": "会影响己方技能", "requires_occupied_station": "需要站点被占用", "damage_threshold_by_level": "伤害阈值",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def visible_component(profile: dict[str, Any]) -> bool:
    return not bool((profile["component"].get("availability") or {}).get("vu_only"))


def lv50_text(profile: dict[str, Any]) -> str:
    value = (profile["component"].get("level_values") or {}).get("50")
    if not value:
        return "Lv50未记载"
    raw = value.get("value_raw")
    return str(raw) if raw not in (None, "") else "效果未记载"


def probability_text(profile: dict[str, Any]) -> str:
    value = (profile["activation"].get("probability_by_level") or {}).get("50")
    if not value:
        return ""
    if value.get("parse_status") == "exact":
        return f"{value['percent']:g}%"
    if value.get("parse_status") == "range":
        return f"{value['min_percent']:g}%~{value['max_percent']:g}%"
    raw = value.get("raw")
    return json.dumps(raw, ensure_ascii=False) if raw else "概率未记载"


def time_text(profile: dict[str, Any], field: str) -> str:
    value = (profile["activation"].get(f"{field}_by_level") or {}).get("50") or {}
    return str(value.get("raw") or "")


def component_text(profile: dict[str, Any]) -> str:
    component = profile["component"]
    parts = [EFFECT_ZH.get(component["effect_kind"], component["effect_kind"])]
    recipients = [SCOPE_ZH.get(item, item) for item in component.get("recipient") or []]
    if recipients:
        parts.append("对象：" + "、".join(recipients))
    parts.append("Lv50：" + lv50_text(profile))
    probability = probability_text(profile)
    if probability:
        parts.append("概率：" + probability)
    duration = time_text(profile, "duration")
    cooldown = time_text(profile, "cooldown")
    if duration:
        parts.append("持续：" + duration)
    if cooldown:
        parts.append("CD：" + cooldown)
    if (component.get("availability") or {}).get("vu_only"):
        parts.append("仅VU")
    return "；".join(parts)


def constraint_text(profile: dict[str, Any]) -> str:
    items = profile["constraints"].get("hard") or []
    labels = []
    for item in items:
        key = str(item.get("key") or "")
        labels.append(CONSTRAINT_ZH.get(key, key))
    costs = [COST_ZH.get(item, item) for item in profile["constraints"].get("opportunity_costs") or []]
    return "、".join(dict.fromkeys([*labels, *costs])) or "无额外限制已结构化"


def prior_index() -> dict[str, list[dict[str, Any]]]:
    if not PRIOR_AUDIT.exists():
        return {}
    audit = json.loads(PRIOR_AUDIT.read_text(encoding="utf-8"))
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in audit.get("rows") or []:
        index[str(row.get("denko_id"))].append(row)
    return index


def prior_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "未列入新手推荐页"
    findings = [finding for row in rows for finding in row.get("findings") or []]
    if not findings:
        return "推荐先验：与详情事实核对通过"
    reasons = "；".join(str(item.get("reason_zh")) for item in findings)
    return "推荐先验提示：" + reasons


def grouped_rows(profiles: list[dict[str, Any]], scene: str, priors: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for profile in profiles:
        if not visible_component(profile):
            continue
        if scene in {tag["id"] for tag in profile.get("scene_tags") or []}:
            grouped[profile["denko"]["denko_id"]].append(profile)
    rows = []
    for denko_id, items in grouped.items():
        denko = items[0]["denko"]
        rows.append({
            "denko": denko,
            "items": sorted(items, key=lambda item: item["profile_id"]),
            "prior": prior_text(priors.get(denko_id, [])),
            "review": any(item["record_meta"].get("needs_review") for item in items),
        })
    return sorted(rows, key=lambda row: row["denko"]["denko_id"])


def render() -> str:
    profiles = read_jsonl(PROFILES)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    priors = prior_index()
    sections = {scene_id: grouped_rows(profiles, scene_id, priors) for scene_id, _, _ in SCENES}
    tab_buttons = "".join(
        f'<button class="tab" data-tab="{scene_id}">{title}<span>{len(sections[scene_id])}</span></button>'
        for scene_id, title, _ in SCENES
    )
    body = []
    for scene_id, title, description in SCENES:
        rows = sections[scene_id]
        body.append(f'<section class="panel" id="{scene_id}"><h2>{esc(title)}</h2><p class="desc">{esc(description)} 不代表通用强度，必须同时看限制与实际队伍条件。</p>')
        body.append('<table><thead><tr><th>でんこ</th><th>属性 / 类型</th><th>本场景可用组件（Lv50）</th><th>触发与主要限制</th><th>推荐页核对</th></tr></thead><tbody>')
        for row in rows:
            denko = row["denko"]
            items = row["items"]
            components = "<br>".join(esc(component_text(item)) for item in items)
            constraints = "<br>".join(esc(constraint_text(item)) for item in items)
            url = items[0]["record_meta"].get("source_url") or "#"
            review = '<span class="review">待自动复查</span>' if row["review"] else ""
            body.append(
                f'<tr data-search="{esc(denko["denko_id"] + " " + str(denko.get("name") or "") + " " + components + " " + constraints)}">'
                f'<td><a href="{esc(url)}" target="_blank" rel="noreferrer"><code>{esc(denko["denko_id"])}</code><br>{esc(denko.get("name"))}</a>{review}</td>'
                f'<td>{esc(denko.get("attribute") or "-")}<br>{esc(denko.get("type") or "-")}</td>'
                f'<td>{components}</td><td>{constraints}</td><td>{esc(row["prior"])}</td></tr>'
            )
        body.append('</tbody></table></section>')
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ekimemo Step3 场景角色画像</title>
<style>
:root{{color-scheme:light;font-family:system-ui,"Microsoft YaHei",sans-serif;color:#172033;background:#f7f8fa}}*{{box-sizing:border-box}}body{{margin:0}}header{{padding:22px max(22px,calc((100vw - 1520px)/2));background:#fff;border-bottom:1px solid #dfe3e8}}h1{{font-size:26px;margin:8px 0}}h2{{font-size:20px;margin:20px 0 6px}}p{{line-height:1.6}}a{{color:#075f9c;text-decoration:none}}a:hover{{text-decoration:underline}}code{{font-family:ui-monospace,Consolas,monospace;font-size:12px}}.back{{font-size:13px}}.meta,.desc{{font-size:13px;color:#56616d;margin:6px 0}}.tabs{{display:flex;gap:6px;flex-wrap:wrap;margin-top:16px}}button{{font:inherit}}.tab{{background:#fff;border:1px solid #c8d0d8;border-radius:4px;padding:7px 10px;cursor:pointer;color:#263342}}.tab.active{{background:#1261a0;border-color:#1261a0;color:#fff}}.tab span{{font-size:11px;margin-left:6px;opacity:.8}}main{{padding:0 max(22px,calc((100vw - 1520px)/2)) 32px}}.tools{{padding:16px 0;border-bottom:1px solid #dfe3e8}}input{{width:min(360px,100%);padding:8px;border:1px solid #bdc7d1;border-radius:4px;font:inherit}}.panel{{display:none}}.panel.active{{display:block}}table{{border-collapse:collapse;width:100%;background:#fff;margin-top:12px;table-layout:fixed}}th,td{{border:1px solid #d9e0e6;padding:8px;vertical-align:top;text-align:left;font-size:13px;line-height:1.55;word-break:break-word}}th{{background:#eef2f6}}th:nth-child(1){{width:150px}}th:nth-child(2){{width:120px}}th:nth-child(4){{width:220px}}th:nth-child(5){{width:240px}}.review{{display:block;font-size:11px;color:#9d5412;margin-top:4px}}.hidden{{display:none}}@media(max-width:850px){{header,main{{padding-left:12px;padding-right:12px}}table{{table-layout:auto;min-width:980px}}.panel{{overflow:auto}}}}
</style></head><body>
<header><a class="back" href="../../docs/reports/index.html">返回报表目录</a><h1>Ekimemo Step3 场景角色画像</h1><p class="meta">基于 Step1 详情页事实自动生成。共 {manifest['counts']['profiles']} 个技能组件；本页按场景归类，不提供全局强度总分。推荐页仅作独立先验核对，不能覆盖详情事实。</p><p class="meta">外部策略参考（均已于 2025-05-07 停更，仅作场景与条件成本先验）：<a href="https://3secondsgameover.com/e/ekimemo_attacker" target="_blank" rel="noreferrer">アタッカーまとめ</a>、<a href="https://3secondsgameover.com/e/ekimemo_hensei" target="_blank" rel="noreferrer">オススメ編成まとめ</a>。</p><div class="tabs">{tab_buttons}</div></header>
<main><div class="tools"><input id="search" placeholder="搜索 ID、名字、效果或条件"></div>{''.join(body)}</main>
<script>
const tabs=[...document.querySelectorAll('.tab')],panels=[...document.querySelectorAll('.panel')];function select(id){{tabs.forEach(x=>x.classList.toggle('active',x.dataset.tab===id));panels.forEach(x=>x.classList.toggle('active',x.id===id));document.querySelector('#search').dispatchEvent(new Event('input'));}}tabs.forEach(x=>x.onclick=()=>select(x.dataset.tab));select('{SCENES[0][0]}');document.querySelector('#search').oninput=e=>{{const q=e.target.value.trim().toLowerCase();document.querySelectorAll('.panel.active tbody tr').forEach(row=>row.classList.toggle('hidden',q&&!row.dataset.search.toLowerCase().includes(q)));}};
</script></body></html>'''


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render().replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    print(json.dumps({"report": str(OUT.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
