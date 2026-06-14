from __future__ import annotations

import html
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import parse as base


AUDIT_JSON = base.ROOT / "data" / "agent_runs" / "original_001_163_report_checklist_audit.json"
OUT_HTML = base.ROOT / "data" / "reports" / "original_001_163_full_audit_zh.html"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def write_html_entity(path: Path, lines: list[str]) -> None:
    text = "\n".join(lines).encode("ascii", "xmlcharrefreplace").decode("ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


def batch_rows() -> list[dict[str, Any]]:
    rows = []
    for state_path in sorted((base.ROOT / "data" / "agent_runs").glob("original_*_cycle_state.json")):
        if "001_163" in state_path.name:
            continue
        state = read_json(state_path)
        rows.append(
            {
                "batch": state_path.name.replace("_cycle_state.json", ""),
                "skill_records": state.get("metrics", {}).get("skill_records"),
                "blocking_item_count": state.get("metrics", {}).get("blocking_item_count"),
                "component_review_reason_counts": state.get("metrics", {}).get("component_review_reason_counts", {}),
                "report": state.get("paths", {}).get("report"),
            }
        )
    return rows


def patch_counts() -> list[dict[str, Any]]:
    out = []
    for patch_path in sorted((base.ROOT / "data" / "manual_fills").glob("original_*_semantic_patches.jsonl")):
        rows = read_jsonl(patch_path)
        out.append(
            {
                "file": str(patch_path.relative_to(base.ROOT)),
                "patch_count": len(rows),
                "accepted_count": sum(1 for row in rows if row.get("status") == "accepted"),
            }
        )
    return out


def main() -> int:
    audit = read_json(AUDIT_JSON)
    issues = audit.get("issues", [])
    severity_counts = Counter(issue.get("severity") for issue in issues)
    category_counts = Counter(issue.get("category") for issue in issues)
    lines = [
        "<!doctype html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>Original 001-163 全量清理审计报告</title>",
        "<style>body{font-family:system-ui,sans-serif;line-height:1.55;margin:24px;color:#1f2328}table{border-collapse:collapse;width:100%;margin:12px 0 24px}th,td{border:1px solid #d0d7de;padding:6px 8px;vertical-align:top}th{background:#f6f8fa}.ok{color:#116329;font-weight:700}.warn{color:#9a6700;font-weight:700}code{background:#f6f8fa;padding:1px 4px}.small{font-size:12px;color:#57606a}</style>",
        "</head>",
        "<body>",
        "<h1>Original 001-163 全量清理审计报告</h1>",
        f"<p class=\"small\">generated_at: {esc(datetime.now(base.JST).isoformat())}</p>",
        "<h2>结论</h2>",
    ]
    if issues:
        lines.append(f"<p class=\"warn\">仍有 {len(issues)} 个 checklist issue，需要继续复查。</p>")
    else:
        lines.append("<p class=\"ok\">按当前 checklist，001-163 全量报告未检出剩余 issue。</p>")
    lines.extend(
        [
            "<h2>本轮自动处理</h2>",
            "<ul>",
            "<li>重跑 original 001-040、040-080、080-119、120-163 的 parser 与报告。</li>",
            "<li>修正 parser：相手上下文保守结构化、アクセスされて 判为 received、経験値分配独立 effect_kind、リブート进入 CD 不再误判为 reboot 效果。</li>",
            "<li>修正 report：顶部显示 component review 统计，避免 blocking=0 时误导。</li>",
            "<li>修正 probability 抽取：支持 (2) (1)が発動した上で30%、(2)x%、(2)(3) 100% 等格式。</li>",
            "<li>应用 semantic patches：#017、#091、#109、#111 等已落地；PowerShell 日文 literal 造成的问号乱码已通过重跑和 ASCII escaped patch 修复。</li>",
            "</ul>",
            "<h2>最终审计指标</h2>",
            "<table><tbody>",
            f"<tr><th>scope</th><td>{esc(audit.get('scope'))}</td></tr>",
            f"<tr><th>issue_count</th><td>{esc(audit.get('metrics', {}).get('issue_count'))}</td></tr>",
            f"<tr><th>severity_counts</th><td>{esc(dict(severity_counts))}</td></tr>",
            f"<tr><th>category_counts</th><td>{esc(dict(category_counts))}</td></tr>",
            "</tbody></table>",
            "<h2>批次状态</h2>",
            "<table><thead><tr><th>batch</th><th>skill_records</th><th>blocking</th><th>component_review_reasons</th><th>report</th></tr></thead><tbody>",
        ]
    )
    for row in batch_rows():
        lines.append(
            "<tr>"
            f"<td>{esc(row['batch'])}</td>"
            f"<td>{esc(row['skill_records'])}</td>"
            f"<td>{esc(row['blocking_item_count'])}</td>"
            f"<td>{esc(json.dumps(row['component_review_reason_counts'], ensure_ascii=False, sort_keys=True))}</td>"
            f"<td>{esc(row['report'])}</td>"
            "</tr>"
        )
    lines.extend(["</tbody></table>", "<h2>Semantic Patch</h2>", "<table><thead><tr><th>file</th><th>patch_count</th><th>accepted_count</th></tr></thead><tbody>"])
    for row in patch_counts():
        lines.append(
            "<tr>"
            f"<td>{esc(row['file'])}</td>"
            f"<td>{esc(row['patch_count'])}</td>"
            f"<td>{esc(row['accepted_count'])}</td>"
            "</tr>"
        )
    lines.append("</tbody></table>")
    lines.append("<h2>剩余 Issue</h2>")
    if issues:
        lines.append("<table><thead><tr><th>severity</th><th>batch</th><th>denko</th><th>component</th><th>issue</th><th>理由</th></tr></thead><tbody>")
        for issue in issues:
            denko = " ".join(part for part in [issue.get("denko_id"), issue.get("name")] if part)
            lines.append(
                "<tr>"
                f"<td>{esc(issue.get('severity'))}</td>"
                f"<td>{esc(issue.get('batch'))}</td>"
                f"<td>{esc(denko)}</td>"
                f"<td>{esc(issue.get('component_id'))}</td>"
                f"<td>{esc(issue.get('issue'))}</td>"
                f"<td>{esc(issue.get('detail_zh'))}</td>"
                "</tr>"
            )
        lines.append("</tbody></table>")
    else:
        lines.append("<p>无。</p>")
    lines.extend(
        [
            "<h2>保留风险</h2>",
            "<p>当前清零的是已沉淀 checklist 的自动审计项；component_semantics_need_review 仍表示这些组件保留了通用语义复核标记，不等价于所有游戏机制已经完全 solver-ready。</p>",
            "</body></html>",
        ]
    )
    write_html_entity(OUT_HTML, lines)
    print(json.dumps({"report": str(OUT_HTML.relative_to(base.ROOT)), "issue_count": len(issues)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
