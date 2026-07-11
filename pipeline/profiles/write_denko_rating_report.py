from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RATINGS = ROOT / "data/role_profiles/denko_ratings.jsonl"
MANIFEST = ROOT / "data/role_profiles/rating_manifest.json"
OUT = ROOT / "data/reports/step3_denko_ratings_zh.html"
LLM_REVIEWS = [
    ROOT / "data/audits/step3_rating_llm_round1.jsonl",
    ROOT / "data/audits/step3_rating_llm_round2.jsonl",
]
SCENES = [
    ("daily_attack", "无脑打站"), ("burst_attack", "计划爆发"),
    ("home_defense", "在家守站"), ("expedition_score", "远征积分"),
    ("expedition_exp", "远征经验"), ("growth", "日常育成"),
    ("mechanism", "机制辅助"),
]
ROLES = [("attack", "攻击职责"), ("defense", "防守职责"), ("expedition", "远征职责"), ("growth", "育成职责"), ("mechanism", "机制辅助")]


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
        calibration_detail = ""
        if row["calibration"].get("status") == "mismatch":
            calibration_detail = (
                '<details><summary>模型原始分与 Wiki 不一致</summary>'
                f'<small>Wiki：{esc(row["calibration"].get("wiki_reason_ja") or "-")}</small>'
                f'<small>处理：{esc(row["calibration"].get("reason_zh") or "-")}</small></details>'
            )
        factor_cells = {}
        for level in ("50", "80"):
            component = level_cells[level]["component"]
            factors = component["factors"] if component else {}
            factor_cells[level] = {
                "effect": component["effect_zh"] if component else "—",
                "probability": f"{factors.get('probability', 0) * 100:.0f}%" if component else "—",
                "availability": f"{factors.get('availability', 0) * 100:.0f}%" if component else "—",
                "conditions": "、".join(item["key"] for item in factors.get("condition_details") or []) or "无",
                "scope_cost": (str(factors.get("scope_basis") or "—") + (" / " + "、".join(factors.get("cost_details") or []) if factors.get("cost_details") else "")),
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
            f'<td class="overall"><strong class="g50 grade grade-{level_cells["50"]["grade"]}">{level_cells["50"]["grade"]}</strong><strong class="g80 grade grade-{level_cells["80"]["grade"]}">{level_cells["80"]["grade"]}</strong><b class="s50">{level_cells["50"]["overall"]}</b><b class="s80">{level_cells["80"]["overall"]}</b><small class="s50">模型原始 {level_cells["50"]["model"]}</small></td>'
            f'<td><span class="s50">{esc(level_cells["50"]["top_scene"])} {level_cells["50"]["top_score"]}</span><span class="s80">{esc(level_cells["80"]["top_scene"])} {level_cells["80"]["top_score"]}</span></td>'
            f'<td><span class="s50">{esc(factor_cells["50"]["effect"])}</span><span class="s80">{esc(factor_cells["80"]["effect"])}</span></td>'
            f'<td><span class="s50">{esc(factor_cells["50"]["probability"])}</span><span class="s80">{esc(factor_cells["80"]["probability"])}</span></td>'
            f'<td><span class="s50">{esc(factor_cells["50"]["availability"])}</span><span class="s80">{esc(factor_cells["80"]["availability"])}</span></td>'
            f'<td><span class="s50">{esc(factor_cells["50"]["conditions"])}</span><span class="s80">{esc(factor_cells["80"]["conditions"])}</span></td>'
            f'<td><span class="s50">{esc(factor_cells["50"]["scope_cost"])}</span><span class="s80">{esc(factor_cells["80"]["scope_cost"])}</span></td>'
            f'{role_cells}{scene_cells}<td class="reviewed">{review_html}<small>Wiki 新手标记：{esc(prior)}</small>{calibration_detail}</td></tr>'
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
<p class="meta">共 {manifest['counts']['denko']} 名でんこ。Lv50 是 Wiki 校准的新手推荐分，Lv80 是不受新手标签约束的后期模型分；场景拆开后，不再用一个“常驻权重”解释所有玩法。</p>
<div class="formula"><div><b>组件有效效用</b>固定效果量锚点 × 发动概率 × 场景覆盖 × 成长阶段条件 × 作用范围 × 代价。</div><div><b>七个实际场景</b>无脑打站、计划爆发、在家守站、远征积分、远征经验、日常育成、机制辅助分别计算。</div><div><b>Wiki 校准</b>×/△/○/◎ 决定新手推荐粗区间，事实模型只负责区间内排序；※ 保留为场景型。所有模型分歧均进入审计并保留双方理由。</div></div>
<p class="note">Mileage Class 10、饰品槽/饰品数量、先 Link 成功、今日新站、车站属性分支等条件会随新手/后期和场景使用不同满足率。Lv50 表中同时显示“模型原始分”，便于继续发现 Wiki 与模型的偏差。</p></header>
<main><div class="tools"><button data-level="80" class="active">Lv80 标准</button><button data-level="50">Lv50 入门</button><input id="search" placeholder="搜索 ID、名字、属性、类型或推荐"><select id="grade"><option value="">全部等级</option><option>S</option><option>A</option><option>B</option><option>C</option><option>D</option></select><button id="sortOverall">按总分排序</button></div>
<div class="table-wrap"><table><thead><tr><th>でんこ</th><th>总评</th><th>最强场景</th><th>主效果</th><th>概率</th><th>覆盖</th><th>启动条件</th><th>范围 / 代价</th>{role_heads}{heads}<th>核查评语</th></tr></thead><tbody>{''.join(body)}</tbody></table></div></main>
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
