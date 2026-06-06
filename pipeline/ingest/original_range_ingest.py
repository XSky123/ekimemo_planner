from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import sample_first5_fetch_parse as base


def output_stem(start: int, end: int) -> str:
    return f"original_{start:03d}_{end:03d}"


def read_original_records(start: int, end: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_path = base.RAW_DIR / "sample_original_list.html"
    html_text = base.fetch(base.LIST_PAGES["original"], raw_path)
    return base.parse_list_page(
        "original",
        base.LIST_PAGES["original"],
        html_text,
        limit=None,
        id_min=start,
        id_max=end,
    )


def classify_skill_row(row: dict[str, Any]) -> str:
    meta = row.get("record_meta", {})
    reasons = set(meta.get("review_reasons") or [])
    components = row.get("skill_components") or []
    if not components:
        return "needs_parser_rule"
    if "lv50_skill_row_not_found" in reasons:
        return "needs_parser_rule"
    if any(component.get("confidence") == "low" for component in components):
        return "needs_llm_snippet"
    if meta.get("needs_review"):
        return "needs_manual_review"
    return "parsed_ok"


def batch_slices(records: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    return [records[i : i + batch_size] for i in range(0, len(records), batch_size)]


def component_kind_counts(skill_rows: list[dict[str, Any]]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in skill_rows:
        for component in row.get("skill_components") or []:
            counts[component.get("effect_kind") or "unknown"] += 1
    return counts


def write_html_report(
    start: int,
    end: int,
    denko_rows: list[dict[str, Any]],
    skill_rows: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    batch_size: int,
) -> Path:
    def esc(value: Any) -> str:
        return html.escape("" if value is None else str(value))

    by_id = {row["denko_id"]: row for row in skill_rows}
    classification = Counter(classify_skill_row(row) for row in skill_rows)
    reason_counts: Counter[str] = Counter()
    for row in skill_rows:
        reason_counts.update(row.get("record_meta", {}).get("review_reasons") or [])
    component_counts = component_kind_counts(skill_rows)

    lines = [
        "<!doctype html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>Original {start}-{end} Ingestion Review</title>",
        "<style>body{font-family:system-ui,sans-serif;line-height:1.5;margin:24px}table{border-collapse:collapse;width:100%;margin:12px 0 24px}th,td{border:1px solid #ccc;padding:6px 8px;vertical-align:top}th{background:#f5f5f5}code{background:#f6f8fa;padding:1px 4px}</style>",
        "</head><body>",
        f"<h1>Original {start}-{end} 数据读取报告</h1>",
        "<p>controller-first 执行：本批只使用脚本、缓存与确定性 parser；未调用 LLM。</p>",
        "<h2>批次指标</h2>",
        "<table><tbody>",
        f"<tr><th>范围</th><td>original:{start:03d} - original:{end:03d}</td></tr>",
        f"<tr><th>record_count</th><td>{len(denko_rows)}</td></tr>",
        f"<tr><th>batch_size</th><td>{batch_size}</td></tr>",
        f"<tr><th>review_queue</th><td>{len(reviews)}</td></tr>",
        f"<tr><th>classification</th><td>{esc(dict(classification))}</td></tr>",
        f"<tr><th>review_reasons</th><td>{esc(dict(reason_counts))}</td></tr>",
        f"<tr><th>component_kinds</th><td>{esc(dict(component_counts))}</td></tr>",
        "</tbody></table>",
    ]

    lines.append("<h2>分批复盘</h2>")
    for batch in batch_slices(denko_rows, batch_size):
        batch_ids = [row["identity"]["denko_id"] for row in batch]
        batch_skills = [by_id[denko_id] for denko_id in batch_ids if denko_id in by_id]
        batch_classification = Counter(classify_skill_row(row) for row in batch_skills)
        lines.append(
            f"<p><strong>{esc(batch_ids[0])} - {esc(batch_ids[-1])}</strong>: "
            f"{len(batch)} records, {esc(dict(batch_classification))}</p>"
        )

    lines.append("<h2>技能分量摘要</h2>")
    lines.append(
        "<table><thead><tr><th>denko_id</th><th>name</th><th>skill</th><th>class</th><th>components</th><th>summary_zh</th><th>review_reasons</th></tr></thead><tbody>"
    )
    for denko in denko_rows:
        ident = denko["identity"]
        skill = by_id.get(ident["denko_id"], {})
        component_text = []
        for component in skill.get("skill_components") or []:
            values = component.get("values_by_denko_level") or {}
            lv30 = base.compact_component_value_zh("30", values["30"]) if values.get("30") else ""
            lv50 = base.compact_component_value_zh("50", values["50"]) if values.get("50") else ""
            component_text.append(
                f"{component.get('component_id')} [{', '.join(component.get('target_scope') or [])}] {lv30} {lv50}".strip()
            )
        lines.append(
            "<tr>"
            f"<td>{esc(ident['denko_id'])}</td>"
            f"<td>{esc(ident['name'])}</td>"
            f"<td>{esc(skill.get('skill_name'))}</td>"
            f"<td>{esc(classify_skill_row(skill) if skill else 'missing')}</td>"
            f"<td>{esc(' / '.join(component_text))}</td>"
            f"<td>{esc(skill.get('summary_zh'))}</td>"
            f"<td>{esc(skill.get('record_meta', {}).get('review_reasons'))}</td>"
            "</tr>"
        )
    lines.extend(
        [
            "</tbody></table>",
            "<h2>Controller 判定</h2>",
            "<ul>",
            "<li>本报告中的 <code>needs_manual_review</code> 主要来自样本阶段默认复核标记，不代表全部解析失败。</li>",
            "<li>若同类 review reason 在后续批次重复出现，应优先调整 parser 规则，再考虑 LLM snippet。</li>",
            "<li>本批次输出用于 Step1 数据读取，不启动 solver。</li>",
            "</ul>",
            f"<p>generated_at: {esc(datetime.now(base.JST).isoformat())}</p>",
            "</body></html>",
        ]
    )
    base.REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = base.REPORT_DIR / f"{output_stem(start, end)}_batch_review_zh.html"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, required=True)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--batch-size", type=int, default=30)
    args = parser.parse_args()

    base.RAW_DIR.mkdir(parents=True, exist_ok=True)
    base.RECORD_DIR.mkdir(parents=True, exist_ok=True)
    base.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    base.REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    base.REPORT_DIR.mkdir(parents=True, exist_ok=True)

    denko_rows, reviews = read_original_records(args.start, args.end)
    base.enrich_details(denko_rows, reviews)
    skill_rows = base.build_skill_fact_records(denko_rows)
    reviews.extend(base.build_skill_review_items(skill_rows))

    stem = output_stem(args.start, args.end)
    base.write_jsonl(base.RECORD_DIR / f"{stem}_denko_facts.jsonl", denko_rows)
    base.write_jsonl(base.RECORD_DIR / f"{stem}_skill_facts.jsonl", skill_rows)
    base.write_jsonl(base.REVIEW_DIR / f"{stem}_review_queue.jsonl", reviews)
    index = {
        "schema_version": 1,
        "parser_version": base.PARSER_VERSION,
        "generated_at": datetime.now(base.JST).isoformat(),
        "scope": {"pool": "original", "start": args.start, "end": args.end},
        "records": [
            {
                "denko_id": row["identity"]["denko_id"],
                "wiki_no": row["identity"]["wiki_no"],
                "name": row["identity"]["name"],
                "detail_url": row["identity"]["detail_url"],
            }
            for row in denko_rows
        ],
    }
    (base.INDEX_DIR / f"{stem}_denko_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    report_path = write_html_report(args.start, args.end, denko_rows, skill_rows, reviews, args.batch_size)
    print(
        json.dumps(
            {
                "denko_records": len(denko_rows),
                "skill_records": len(skill_rows),
                "reviews": len(reviews),
                "report": str(report_path.relative_to(base.ROOT)),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
