from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "reports" / "step4_solver_examples_zh.html"

SCENE_ZH = {
    "capture": "突破/抢站", "defense": "守站", "commute": "通勤低操作", "expedition": "远征/连续 link",
    "visit_count_event": "回数活动", "score_exp": "积分/经验", "growth": "成长", "mechanism": "机制与干扰",
}
EFFECT_ZH = {
    "atk_buff": "ATK增加", "ap_buff": "AP增加", "fixed_damage": "固定伤害", "additional_fixed_damage": "追加固定伤害",
    "def_debuff": "降低对手DEF", "ap_debuff": "降低对手AP", "skill_disable": "技能无效化", "skill_effect_nullification": "技能效果无效化",
    "force_hp_zero": "HP归零", "def_buff": "DEF增加", "atk_debuff": "降低对手ATK", "damage_reduction": "伤害轻减",
    "hp_recovery": "HP回复", "hp_recovery_bonus": "回复强化", "survive_hp1": "保留1HP", "damage_nullification": "伤害无效化",
    "damage_cap": "伤害上限", "damage_substitution": "伤害替代", "link_continue": "link持续", "link_retention": "link保持",
    "counter": "反击", "counter_damage": "反击伤害", "reboot": "reboot", "exp_gain": "经验获取", "score_gain": "积分获取",
    "extra_access": "追加访问", "random_previous_station_access": "随机访问", "remote_station_access": "远程访问",
}
METRIC_ZH = {
    "atk_percent": "ATK%", "ap_percent": "AP%", "fixed_damage": "固定伤害", "enemy_def_debuff_percent": "对手DEF下降%",
    "enemy_ap_debuff_percent": "对手AP下降%", "skill_interference": "妨害效果", "def_percent": "DEF%",
    "enemy_atk_debuff_percent": "对手ATK下降%", "damage_reduction": "伤害轻减", "hp_recovery": "HP回复",
    "hp_recovery_bonus": "回复强化", "survival_effect": "生存效果", "link_retention": "link保持",
    "exp_gain": "经验", "score_gain": "积分", "extra_access": "追加访问", "access_tool": "访问工具",
    "radar_range": "雷达范围", "cooldown_operation": "CD操作", "probability_operation": "概率操作",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def metric_text(metrics: dict[str, float]) -> str:
    if not metrics:
        return "无可比较数值"
    return " / ".join(f"{METRIC_ZH.get(key, key)} +{value:g}" for key, value in metrics.items())


def component_rows(team: dict[str, Any]) -> str:
    rows: list[str] = []
    for component in team["active_components"]:
        source = component.get("source_url")
        holder = esc(component["denko_name"])
        name = esc(EFFECT_ZH.get(component["effect_kind"], component["effect_kind"]))
        source_html = f'<a href="{esc(source)}" target="_blank" rel="noreferrer">wiki页</a>' if source else ""
        value = "未量化" if component["status"] == "active_unquantified" else f"最大 {component['theoretical_max']:g} / 期望 {component['expected_value']:g}"
        probability = "" if component.get("probability_factor") in (None, 1.0) else f"概率系数 {component['probability_factor']:g}"
        warning = "；".join(component.get("warnings_zh") or [])
        condition = esc("；".join(item for item in [str(component.get("condition_raw") or ""), warning] if item))
        rows.append(f"<tr><td>{holder}</td><td>{name}</td><td>{esc('、'.join(component.get('recipient') or []))}</td><td>{esc(value)} {esc(probability)}</td><td>{condition}</td><td>{source_html}</td></tr>")
    return "".join(rows) or "<tr><td colspan=6>没有可确认的直接贡献</td></tr>"


def inactive_rows(team: dict[str, Any]) -> str:
    rows: list[str] = []
    for component in team["inactive_components"]:
        name = esc(EFFECT_ZH.get(component["effect_kind"], component["effect_kind"]))
        reason = esc("；".join(component.get("reasons_zh") or []))
        rows.append(f"<li><b>{esc(component['denko_name'])}</b> 的 {name}：{reason}</li>")
    return "".join(rows) or "<li>无</li>"


def render_result(result: dict[str, Any]) -> str:
    request = result["request"]
    scene = SCENE_ZH.get(request["scene"], request["scene"])
    cards: list[str] = []
    for index, team in enumerate(result["teams"], 1):
        members = "　".join(f"<b>{esc(member['name'])}</b><small>{esc(member['denko_id'])}{' / ' + str(member['position']) + '号位' if member.get('position') else ''}</small>" for member in team["members"])
        confirmation = "全部已确认" if team["constraints_check"]["all_constraints_confirmed"] else "含待确认条件"
        cards.append(
            f"<article class=team><h3>方案 {index} <span>{confirmation}</span></h3>"
            f"<p class=members>{members}</p>"
            f"<p><b>概率期望：</b>{esc(metric_text(team['metrics']['expected_value']))}<br>"
            f"<b>理论最大：</b>{esc(metric_text(team['metrics']['theoretical_max']))}<br>"
            f"<b>操作成本：</b>{team['operation_cost']}　<b>待确认/未生效：</b>{team['constraints_check']['inactive_or_pending_count']}</p>"
            "<details open><summary>已计入的组件</summary><table><thead><tr><th>持有者</th><th>效果</th><th>对象</th><th>数值</th><th>触发与条件</th><th>来源</th></tr></thead>"
            f"<tbody>{component_rows(team)}</tbody></table></details>"
            f"<details><summary>未计入或待确认的组件 ({team['constraints_check']['inactive_or_pending_count']})</summary><ul>{inactive_rows(team)}</ul></details></article>"
        )
    limitations = "".join(f"<li>{esc(item)}</li>" for item in result["result_meta"].get("limitations_zh") or [])
    return (
        f"<section class=result><h2>{scene}：{esc(request['main_denko_id'])} / Lv{esc(request.get('level', '50'))}</h2>"
        f"<p>候选 {result['candidate_summary']['candidate_pool_size']} 人，枚举 {result['candidate_summary']['enumerated_team_count']} 队，Pareto 前沿 {result['candidate_summary']['pareto_team_count']} 队；页面展示前十个。</p>"
        f"<ul class=limitations>{limitations}</ul>{''.join(cards)}</section>"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a Chinese review report from Step4 solver JSON results")
    parser.add_argument("results", type=Path, nargs="+", help="solver result JSON files")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    results = [read_json(path) for path in args.results]
    body = "".join(render_result(result) for result in results)
    document = f"""<!doctype html>
<html lang=zh-CN><meta charset=utf-8><meta name=viewport content=\"width=device-width,initial-scale=1\">
<title>Ekimemo Step4 配队求解样例</title>
<style>
body{{margin:0;color:#172433;background:#f8fafc;font:14px/1.55 system-ui,-apple-system,\"Segoe UI\",sans-serif}}main{{max-width:1320px;margin:auto;padding:24px}}h1,h2,h3{{margin:.3em 0;color:#102a43;letter-spacing:0}}p{{margin:.55em 0}}a{{color:#076ea8;text-decoration:none;font-weight:600}}.top{{display:flex;justify-content:space-between;gap:16px;align-items:center;border-bottom:1px solid #cbd5e1;padding-bottom:14px}}.note,.limitations{{color:#496174}}.result{{margin:34px 0}}.team{{background:#fff;border:1px solid #cbd5e1;border-radius:7px;margin:14px 0;padding:16px}}.team h3 span{{font-size:12px;color:#236749;font-weight:600;margin-left:8px}}.members{{display:flex;gap:10px;flex-wrap:wrap}}.members b{{color:#0b5e89}}small{{display:block;color:#64748b;font-weight:400}}details{{margin-top:10px}}summary{{cursor:pointer;font-weight:700;color:#173f5f}}table{{border-collapse:collapse;width:100%;margin-top:8px;background:#fff}}th,td{{padding:8px;border:1px solid #d8e1e8;vertical-align:top;text-align:left}}th{{background:#edf4f8;white-space:nowrap}}ul{{padding-left:20px}}@media(max-width:720px){{main{{padding:14px}}.top{{display:block}}table{{font-size:12px}}th,td{{padding:5px}}}}
</style><body><main><div class=top><div><h1>Ekimemo Step4 配队求解样例</h1><p class=note>固定主力下的可解释候选。概率技能按期望值计入；不同量纲不伪造为同一个伤害分数。</p></div><a href=\"../../docs/reports/index.html\">返回报告目录</a></div>{body}</main></body></html>"""
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(document.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
    print(json.dumps({"output": str(args.output), "scenarios": len(results)}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
