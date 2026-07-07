from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT_HTML = ROOT / "data" / "reports" / "step2_all_reports_zh.html"


REPORTS = [
    {
        "id": "attack",
        "title": "攻击辅助排行",
        "file": "step2_attack_support_rankings_zh.html",
        "description": "给自己/队友加 ATK、固定伤害、降低对手 DEF。",
        "height": 920,
    },
    {
        "id": "defense",
        "title": "防御/守站辅助排行",
        "file": "step2_defense_support_rankings_zh.html",
        "description": "DEF、减伤、HP 回复、无效化/保命、降低对手输出、link 保持。",
        "height": 920,
    },
    {
        "id": "exp-pt",
        "title": "经验/PT 辅助排行",
        "file": "step2_exp_pt_support_rankings_zh.html",
        "description": "固定经验/score、倍率、ねこぱんち经验、收益技能效果量强化。",
        "height": 920,
    },
    {
        "id": "mobility",
        "title": "位移/访问次数辅助",
        "file": "step2_mobility_visit_rankings_zh.html",
        "description": "额外访问、随机踩站、传送/范围访问、新站奖励。",
        "height": 760,
    },
    {
        "id": "utility",
        "title": "技能工具索引",
        "file": "step2_skill_utility_reports_zh.html",
        "description": "技能干扰/无效化、CD/概率操作、条件索引、活动访问。",
        "height": 900,
    },
    {
        "id": "prototype",
        "title": "原型线路/站点反查",
        "file": "step2_prototype_lookup_zh.html",
        "description": "按线路、车辆、公司、都道府县、生日、声优等反查でんこ。",
        "height": 900,
    },
]


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def main() -> None:
    nav = "\n".join(f'<a href="#{esc(report["id"])}">{esc(report["title"])}</a>' for report in REPORTS)
    cards = "\n".join(
        f"""
        <section id="{esc(report["id"])}" class="report-card">
          <header>
            <div>
              <h2>{esc(report["title"])}</h2>
              <p>{esc(report["description"])}</p>
            </div>
            <a class="open-link" href="{esc(report["file"])}">单独打开</a>
          </header>
          <iframe title="{esc(report["title"])}" src="{esc(report["file"])}" style="height:{int(report["height"])}px"></iframe>
          <a class="back-top" href="#top">返回顶部</a>
        </section>
        """
        for report in REPORTS
    )
    html_text = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ekimemo Step2 综合报表</title>
  <style>
    body {{ margin: 24px; color: #1f2328; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; line-height: 1.5; background: #ffffff; }}
    #top {{ max-width: 1180px; margin: 0 auto; }}
    h1 {{ margin: 0 0 8px; font-size: 28px; }}
    h2 {{ margin: 0; font-size: 20px; }}
    p {{ margin: 6px 0 0; color: #57606a; }}
    .nav {{ position: sticky; top: 0; z-index: 5; display: flex; gap: 8px; flex-wrap: wrap; padding: 12px 0; margin: 16px 0; background: white; border-bottom: 1px solid #d8dee4; }}
    .nav a, .open-link, .back-top {{ color: #0969da; text-decoration: none; font-weight: 600; }}
    .nav a {{ border: 1px solid #d0d7de; border-radius: 4px; padding: 7px 10px; background: #f6f8fa; }}
    .report-card {{ margin: 22px 0 36px; border-top: 1px solid #d8dee4; padding-top: 16px; }}
    .report-card header {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 10px; }}
    .open-link {{ white-space: nowrap; border: 1px solid #d0d7de; border-radius: 4px; padding: 6px 9px; background: white; }}
    iframe {{ width: 100%; border: 1px solid #d8dee4; border-radius: 6px; background: white; }}
    .back-top {{ display: inline-block; margin-top: 8px; }}
  </style>
</head>
<body>
  <main id="top">
    <h1>Ekimemo Step2 综合报表</h1>
    <p>一个页面集中浏览当前 Step2 成果。各区块保留原报告的搜索、筛选、排序能力；需要全屏查看时可以单独打开。</p>
    <nav class="nav">{nav}</nav>
    {cards}
  </main>
</body>
</html>
"""
    OUT_HTML.write_text("\n".join(line.rstrip() for line in html_text.splitlines()) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"out": str(OUT_HTML.relative_to(ROOT)), "reports": len(REPORTS)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
