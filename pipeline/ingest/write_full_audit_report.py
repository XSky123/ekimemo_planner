from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import parse as base


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


def default_audit_json(pool: str) -> Path:
    suffix = "001_163" if pool == "original" else "full"
    return base.ROOT / "data" / "agent_runs" / f"{pool}_{suffix}_report_checklist_audit.json"


def default_out_html(pool: str) -> Path:
    if pool == "original":
        return base.ROOT / "data" / "reports" / "original_001_163_full_audit_zh.html"
    return base.ROOT / "data" / "reports" / f"{pool}_full_audit_zh.html"


def batch_rows(pool: str) -> list[dict[str, Any]]:
    rows = []
    for state_path in sorted((base.ROOT / "data" / "agent_runs").glob(f"{pool}_*_cycle_state.json")):
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


def patch_counts(pool: str) -> list[dict[str, Any]]:
    out = []
    for patch_path in sorted((base.ROOT / "data" / "manual_fills").glob(f"{pool}_*_semantic_patches.jsonl")):
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", choices=sorted(base.LIST_PAGES), default="original")
    parser.add_argument("--audit-json", type=Path)
    parser.add_argument("--out-html", type=Path)
    args = parser.parse_args()
    audit_json = args.audit_json or default_audit_json(args.pool)
    out_html = args.out_html or default_out_html(args.pool)
    audit = read_json(audit_json)
    issues = audit.get("issues", [])
    severity_counts = Counter(issue.get("severity") for issue in issues)
    category_counts = Counter(issue.get("category") for issue in issues)
    title = f"{args.pool} 全量清理审计报告"

    lines = [
        "<!doctype html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{esc(title)}</title>",
        "<style>body{font-family:system-ui,sans-serif;line-height:1.55;margin:24px;color:#1f2328}table{border-collapse:collapse;width:100%;margin:12px 0 24px}th,td{border:1px solid #d0d7de;padding:6px 8px;vertical-align:top}th{background:#f6f8fa}.ok{color:#116329;font-weight:700}.warn{color:#9a6700;font-weight:700}.bad{color:#cf222e;font-weight:700}code{background:#f6f8fa;padding:1px 4px}.small{font-size:12px;color:#57606a}</style>",
        "</head>",
        "<body>",
        f"<h1>{esc(title)}</h1>",
        f"<p class=\"small\">generated_at: {esc(datetime.now(base.JST).isoformat())}</p>",
        "<h2>结论</h2>",
    ]
    if issues:
        lines.append(f"<p class=\"warn\">仍有 {len(issues)} 个 checklist issue，已保留在下方表格供下一轮 parser/语义修复。</p>")
    else:
        lines.append("<p class=\"ok\">按当前 checklist，未检出剩余 issue。</p>")

    lines.extend(
        [
            "<h2>审计指标</h2>",
            "<table><tbody>",
            f"<tr><th>scope</th><td>{esc(audit.get('scope'))}</td></tr>",
            f"<tr><th>skill_records</th><td>{esc(audit.get('metrics', {}).get('skill_record_count'))}</td></tr>",
            f"<tr><th>issue_count</th><td>{esc(audit.get('metrics', {}).get('issue_count'))}</td></tr>",
            f"<tr><th>severity_counts</th><td>{esc(dict(severity_counts))}</td></tr>",
            f"<tr><th>category_counts</th><td>{esc(dict(category_counts))}</td></tr>",
            "</tbody></table>",
            "<h2>批次状态</h2>",
            "<table><thead><tr><th>batch</th><th>skill_records</th><th>blocking</th><th>component_review_reasons</th><th>report</th></tr></thead><tbody>",
        ]
    )
    for row in batch_rows(args.pool):
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
    for row in patch_counts(args.pool):
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
        lines.append("<table><thead><tr><th>severity</th><th>batch</th><th>denko</th><th>component</th><th>issue</th><th>理由</th><th>修复提示</th></tr></thead><tbody>")
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
                f"<td>{esc(issue.get('fix_hint_zh'))}</td>"
                "</tr>"
            )
        lines.append("</tbody></table>")
    else:
        lines.append("<p>无。</p>")

    lines.extend(
        [
            "<h2>保留风险</h2>",
            "<p>这里清零的是 checklist 能自动识别的问题；`component_semantics_need_review` 仍表示该 component 保留通用语义复核标记，不等价于 solver-ready。</p>",
            "</body></html>",
        ]
    )
    write_html_entity(out_html, lines)
    print(json.dumps({"report": str(out_html.relative_to(base.ROOT)), "issue_count": len(issues)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
