from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RATINGS = ROOT / "data/role_profiles/denko_ratings.jsonl"
MANIFEST = ROOT / "data/role_profiles/rating_manifest.json"
OUT = ROOT / "data/reports/step3_denko_ratings_zh.html"
LLM_REVIEWS = [ROOT / "data/audits/step3_rating_iteration_5_reviews.jsonl"]
SCOPE_ZH = {
    "accessed_denko": "被访问角色", "accessing_denko": "访问角色", "front_car": "队伍首位",
    "master": "玩家", "master_account": "玩家账号", "opponent_denko": "对手角色",
    "opponent_team": "对方队伍", "own_front_car": "己方首位", "own_skill_effects": "自身技能效果",
    "own_team": "己方队伍", "relative_car": "相对位置角色", "self": "自身", "team_all": "全队",
}
COST_ZH = {
    "context_or_formation_constraint": "场景或编成限制", "long_cooldown": "长冷却",
    "manual_activation": "需要手动启动", "probabilistic": "概率发动", "self_debuff": "附带自身减益",
}
CONDITION_EXACT_ZH = {
    "basis": "计算基准", "source": "效果来源", "state": "状态限定", "operator": "比较方式",
    "frequency": "发动次数限制", "item": "指定道具", "keyword": "指定关键词", "destination": "目的地限定",
    "exclude_self": "不含自身", "formation_only": "仅编成内", "formation_required": "需要指定编成",
    "not_rebooted": "尚未重启", "hp_zero": "HP 为 0", "weather": "天气限定", "weekday": "星期限定",
    "weekday_dependent": "效果随星期变化", "time_window": "时段限定", "season_months": "月份限定",
    "position_rule": "队列位置限定", "position_relative_to_self": "相对自身的位置限定",
    "relative_position": "相对位置限定", "probability_basis": "发动率计算基准",
    "progression_stage": "养成阶段限定", "requires_link_success": "需要先取得 Link",
    "requires_occupied_station": "需要目标站已被占领", "station_is_today_new": "仅今日新站",
    "station_ownership": "车站持有状态限定", "station_attribute": "车站属性限定",
    "same_attribute_station": "需要同属性车站", "accessory_skill_tag": "指定饰品技能标签",
    "accessory_slot_progression_required": "需要解锁饰品槽", "own_skill_conflict": "与自身其他技能冲突",
    "ends_own_team_active_skills": "会结束己方已启动技能", "excluded_when_footbar": "使用 Footbar 时无效",
    "film_skill_effects_excluded": "不计入装扮技能效果", "mutually_exclusive_branch_group": "效果分支互斥",
    "scaling_from_zero": "从零开始累积", "scaling_from_low_or_zero": "低值或零值起算",
}


def condition_label(key: str) -> str:
    if key in CONDITION_EXACT_ZH:
        return CONDITION_EXACT_ZH[key]
    if key.endswith("_raw"):
        if "time" in key: return "原文时段限定"
        if "weekday" in key: return "原文星期限定"
        if "season" in key: return "原文月份限定"
        if "position" in key: return "原文位置例外"
        if "debuff" in key: return "原文减益说明"
        if "station" in key: return "原文车站限定"
        if "opponent" in key: return "原文对手限定"
        return "原文补充限定"
    categories = [
        (("accessory", "equipped"), "饰品限定"), (("attribute",), "属性限定"),
        (("type",), "角色类型限定"), (("opponent",), "对手条件"), (("own_team", "formation"), "己方编成条件"),
        (("station", "link"), "车站或 Link 条件"), (("distance", "travel"), "距离条件"),
        (("hp", "damage"), "HP 或伤害条件"), (("temperature",), "气温条件"),
        (("time", "recent", "previous"), "时间窗口条件"), (("count", "cap", "minimum", "min_", "max_"), "数量门槛"),
        (("skill", "component", "effect"), "技能联动条件"), (("pool", "rank"), "角色池或等级条件"),
        (("outcome", "failure", "reboot"), "访问结果条件"),
    ]
    for needles, label in categories:
        if any(needle in key for needle in needles):
            return label
    return "其他结构化条件"
SCENES = [
    ("daily_attack", "无脑打站"), ("burst_attack", "计划爆发"),
    ("home_defense", "在家守站"), ("expedition_score", "远征积分"),
    ("expedition_exp", "远征经验"), ("growth", "日常育成"),
    ("mechanism", "机制辅助"),
]
ROLES = [("attack", "攻击职责"), ("defense", "防守职责"), ("support", "辅助职责"), ("expedition", "远征职责"), ("growth", "育成职责"), ("mechanism", "机制职责")]


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""), quote=True)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def factor_summary(component: dict[str, Any] | None) -> str:
    if not component:
        return "无结构化技能贡献"
    factors = component["factors"]
    magnitude = factors.get("magnitude_value")
    magnitude_text = "定性效果" if magnitude is None else f"效果量 {magnitude:g}"
    return (
        f"{component['effect_zh']} · {magnitude_text} · "
        f"概率 {factors['probability'] * 100:.0f}% · "
        f"覆盖 {factors['availability'] * 100:.0f}% · "
        f"条件 {factors['condition'] * 100:.0f}% · "
        f"范围 ×{factors['scope']:.2f}"
    )


def render() -> str:
    rows = read_jsonl(RATINGS)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    reviews: dict[str, list[dict[str, Any]]] = {}
    for path in LLM_REVIEWS:
        if not path.exists():
            continue
        for item in read_jsonl(path):
            reviews.setdefault(item["denko_id"], []).append(item)
    body = []
    for row in rows:
        denko = row["denko"]
        level_cells = {}
        for level in ("50", "80"):
            result = row["levels"][level]
            ranked = sorted(result["scenes"].items(), key=lambda item: (-item[1]["score"], item[0]))
            top_scene, top_payload = ranked[0]
            top_component = top_payload["top_components"][0] if top_payload["top_components"] else None
            scores = {scene: payload["score"] for scene, payload in result["scenes"].items()}
            level_cells[level] = {
                "overall": result.get("published_score", result["overall_score"]), "model": result.get("model_score", result["overall_score"]), "grade": result["grade"],
                "top_scene": dict(SCENES)[top_scene], "top_score": top_payload["score"],
                "factor": factor_summary(top_component), "component": top_component, "scores": scores, "roles": result.get("role_scores") or {},
            }
        scene_cells = "".join(
            f'<td class="scene" data-scene="{scene}"><span class="s50">{level_cells["50"]["scores"][scene]}</span><span class="s80">{level_cells["80"]["scores"][scene]}</span></td>'
            for scene, _ in SCENES
        )
        role_cells = "".join(
            f'<td class="scene role" data-scene="role-{role}"><span class="s50">{level_cells["50"]["roles"].get(role, 0)}</span><span class="s80">{level_cells["80"]["roles"].get(role, 0)}</span></td>'
            for role, _ in ROLES
        )
        prior = row["calibration"].get("beginner_prior_marker") or "—"
        wiki_comment = row["calibration"].get("wiki_reason_ja")
        calibration_detail = f'<small>Wiki 评语：{esc(wiki_comment)}</small>' if wiki_comment else ""
        factor_cells = {}
        for level in ("50", "80"):
            component = level_cells[level]["component"]
            factors = component["factors"] if component else {}
            factor_cells[level] = {
                "effect": component["effect_zh"] if component else "—",
                "probability": f"{factors.get('probability', 0) * 100:.0f}%" if component else "—",
                "availability": f"{factors.get('availability', 0) * 100:.0f}%" if component else "—",
                "conditions": "、".join(dict.fromkeys(condition_label(str(item["key"])) for item in factors.get("condition_details") or [])) or "无",
                "scope_cost": (
                    SCOPE_ZH.get(str(factors.get("scope_basis")), "未知范围")
                    + (" / " + "、".join(COST_ZH.get(str(item), "其他使用代价") for item in factors.get("cost_details") or []) if factors.get("cost_details") else " / 无额外代价")
                ),
            }
        reviewed_items = reviews.get(row["rating_id"], [])
        comments = list(dict.fromkeys(
            item["llm_review"]["review_zh"]
            for item in reviewed_items
            if item["llm_review"]["verdict"] != "pass"
        ))
        if comments:
            review_html = "".join(f'<div class="review-item">{esc(comment)}</div>' for comment in comments)
        elif reviewed_items:
            review_html = '<span class="muted">极端样本核查未发现异常</span>'
        else:
            review_html = '<span class="muted">暂无专项核查评语</span>'
        search = " ".join([row["rating_id"], str(denko.get("name") or ""), str(denko.get("attribute") or ""), str(denko.get("type") or ""), row["recommendation_zh"]])
        body.append(
            f'<tr data-search="{esc(search.lower())}" data-score50="{level_cells["50"]["overall"]}" data-score80="{level_cells["80"]["overall"]}">'
            f'<td class="identity"><a href="{esc(row["record_meta"].get("source_url") or "#")}" target="_blank" rel="noreferrer"><code>{esc(row["rating_id"])}</code><br>{esc(denko.get("name"))}</a><small>{esc(denko.get("attribute") or "-")} · {esc(denko.get("type") or "-")}</small></td>'
            f'<td class="overall"><strong class="g50 grade grade-{level_cells["50"]["grade"]}">{level_cells["50"]["grade"]}</strong><strong class="g80 grade grade-{level_cells["80"]["grade"]}">{level_cells["80"]["grade"]}</strong><b class="s50">{level_cells["50"]["overall"]}</b><b class="s80">{level_cells["80"]["overall"]}</b></td>'
            f'<td><span class="s50">{esc(level_cells["50"]["top_scene"])} {level_cells["50"]["top_score"]}</span><span class="s80">{esc(level_cells["80"]["top_scene"])} {level_cells["80"]["top_score"]}</span></td>'
            f'<td><span class="s50">{esc(factor_cells["50"]["effect"])}</span><span class="s80">{esc(factor_cells["80"]["effect"])}</span></td>'
            f'<td><span class="s50">{esc(factor_cells["50"]["probability"])}</span><span class="s80">{esc(factor_cells["80"]["probability"])}</span></td>'
            f'<td><span class="s50">{esc(factor_cells["50"]["availability"])}</span><span class="s80">{esc(factor_cells["80"]["availability"])}</span></td>'
            f'<td><span class="s50">{esc(factor_cells["50"]["conditions"])}</span><span class="s80">{esc(factor_cells["80"]["conditions"])}</span></td>'
            f'<td><span class="s50">{esc(factor_cells["50"]["scope_cost"])}</span><span class="s80">{esc(factor_cells["80"]["scope_cost"])}</span></td>'
            f'{role_cells}{scene_cells}<td class="recommend">{esc(row["recommendation_zh"])}</td><td class="reviewed">{review_html}<small>Wiki 新手标记：{esc(prior)}</small>{calibration_detail}</td></tr>'
        )
    heads = "".join(f'<th data-sort-scene="{scene}">{label}</th>' for scene, label in SCENES)
    role_heads = "".join(f'<th data-sort-scene="role-{role}">{label}</th>' for role, label in ROLES)
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ekimemo Step3 角色综合评分</title>
<style>
:root{{font-family:system-ui,"Microsoft YaHei",sans-serif;color:#172033;background:#f5f7fa}}*{{box-sizing:border-box}}body{{margin:0}}header{{background:#fff;border-bottom:1px solid #dbe1e8;padding:22px max(18px,calc((100vw - 1580px)/2))}}main{{padding:18px max(18px,calc((100vw - 1580px)/2)) 36px}}h1{{margin:8px 0;font-size:27px}}h2{{font-size:18px;margin:22px 0 8px}}p,li{{line-height:1.65}}.back{{font-size:13px;color:#075f9c;text-decoration:none}}.meta,.note{{color:#586574;font-size:13px}}.formula{{display:grid;grid-template-columns:repeat(3,minmax(240px,1fr));gap:10px;margin-top:14px}}.formula div{{background:#f0f4f8;border:1px solid #dbe3ea;border-radius:6px;padding:10px;font-size:13px}}.formula b{{display:block;margin-bottom:4px}}.tools{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:12px}}button,input,select{{font:inherit;border:1px solid #bdc8d3;background:#fff;border-radius:4px;padding:7px 9px}}button{{cursor:pointer}}button.active{{background:#1261a0;color:#fff;border-color:#1261a0}}input{{width:min(340px,100%)}}.table-wrap{{overflow:auto;border:1px solid #d9e0e7;background:#fff}}table{{border-collapse:collapse;width:100%;min-width:1500px}}th,td{{border-bottom:1px solid #e1e6eb;border-right:1px solid #edf0f3;padding:8px;vertical-align:top;text-align:left;font-size:12px;line-height:1.5}}th{{position:sticky;top:0;background:#eaf0f5;z-index:1;white-space:nowrap;cursor:pointer}}tr:hover{{background:#f8fbfd}}td.identity{{width:155px}}td.identity small,td small{{display:block;color:#647180;margin-top:4px}}td.overall{{width:72px;text-align:center}}td.overall b{{font-size:19px;margin-left:5px}}td.scene{{text-align:center;width:58px;font-variant-numeric:tabular-nums}}td.recommend{{width:270px}}a{{color:#075f9c;text-decoration:none}}code{{font-size:11px}}.grade{{display:inline-grid;place-items:center;width:28px;height:28px;border-radius:50%;color:#fff}}.grade-S{{background:#b72f47}}.grade-A{{background:#d17022}}.grade-B{{background:#287a55}}.grade-C{{background:#4779a6}}.grade-D{{background:#78838d}}.s50,.g50{{display:none}}body.lv50 .s50,body.lv50 .g50{{display:inline}}body.lv50 small.s50{{display:block}}body.lv50 .s80,body.lv50 .g80{{display:none}}.hidden{{display:none}}@media(max-width:850px){{header,main{{padding-left:10px;padding-right:10px}}.formula{{grid-template-columns:1fr}}}}
.reviewed{{width:360px}}.review-item{{margin-bottom:7px;padding-bottom:7px;border-bottom:1px dashed #d8dee5}}.verdict{{color:#8b4314}}.muted{{color:#78838d}}
</style></head><body class="lv80">
<header><a class="back" href="../../docs/reports/index.html">返回报表目录</a><h1>Step3 角色综合评分与一句话推荐</h1>
<p class="meta">共 {manifest['counts']['denko']} 名でんこ。Lv50 表示入门养成阶段，Lv80 表示常用满级阶段；Wiki 推荐只作为外部对照，不参与模型打分。</p>
<div class="formula"><div><b>组件有效效用</b>固定效果量锚点 × 发动概率 × 场景覆盖 × 成长阶段条件 × 作用范围 × 代价。</div><div><b>六项职责分</b>攻击、防守、辅助、远征、育成与机制独立排名，避免强力专职角色被无关场景平均拉低。</div><div><b>Wiki 对照</b>×/△/○/◎ 仅用于发现模型与玩家经验的分歧；表中只展示可供读者判断的核查评语。</div></div>
<p class="note">Mileage Class 10、饰品槽/饰品数量、先 Link 成功、今日新站、车站属性分支等条件会随成长阶段和使用场景采用不同满足率。</p></header>
<main><div class="tools"><button data-level="80" class="active">Lv80 标准</button><button data-level="50">Lv50 入门</button><input id="search" placeholder="搜索 ID、名字、属性、类型或推荐"><select id="grade"><option value="">全部等级</option><option>S</option><option>A</option><option>B</option><option>C</option><option>D</option></select><button id="sortOverall">按总分排序</button></div>
<div class="table-wrap"><table><thead><tr><th>でんこ</th><th>总评</th><th>最强场景</th><th>主效果</th><th>概率</th><th>覆盖</th><th>启动条件</th><th>范围 / 代价</th>{role_heads}{heads}<th>一句话推荐</th><th>核查评语</th></tr></thead><tbody>{''.join(body)}</tbody></table></div></main>
<script>
const body=document.body,rows=[...document.querySelectorAll('tbody tr')],tbody=document.querySelector('tbody');let level='80';
function val(row,scene){{if(scene)return +(row.querySelector(`[data-scene="${{scene}}"] .s${{level}}`).textContent);return +row.dataset[`score${{level}}`];}}
function filter(){{const q=document.querySelector('#search').value.trim().toLowerCase(),g=document.querySelector('#grade').value;rows.forEach(r=>{{const rg=r.querySelector(`.g${{level}}`).textContent;r.classList.toggle('hidden',!!q&&!r.dataset.search.includes(q)||!!g&&rg!==g)}})}}
document.querySelectorAll('[data-level]').forEach(b=>b.onclick=()=>{{level=b.dataset.level;body.className=`lv${{level}}`;document.querySelectorAll('[data-level]').forEach(x=>x.classList.toggle('active',x===b));filter()}});
document.querySelector('#search').oninput=filter;document.querySelector('#grade').onchange=filter;
function sort(scene=''){{[...rows].sort((a,b)=>val(b,scene)-val(a,scene)||a.dataset.search.localeCompare(b.dataset.search)).forEach(r=>tbody.appendChild(r))}}document.querySelector('#sortOverall').onclick=()=>sort();document.querySelectorAll('[data-sort-scene]').forEach(th=>th.onclick=()=>sort(th.dataset.sortScene));sort();
</script></body></html>'''


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render().replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    print(json.dumps({"report": str(OUT.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
