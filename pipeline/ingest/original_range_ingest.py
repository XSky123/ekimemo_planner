from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import parse as base


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


COMPONENT_SLOT_COUNT = 5
REPORT_LEVEL_ORDER = ("1", "5", "15", "30", "50", "60", "70", "80", "92", "96", "100", "base")
SUSPICIOUS_REASONS = {
    "key_level_component_missing",
    "labeled_component_count_mismatch",
    "compound_labeled_effect_needs_manual_review",
    "duplicate_labeled_component_values_need_review",
    "condition_effect_mismatch_needs_review",
    "attribute_branch_effect_needs_review",
    "primary_labeled_effect_vu_only_needs_review",
    "vu_label_level_mismatch_needs_review",
}
SUSPICIOUS_REASON_ZH = {
    "key_level_component_missing": "关键等级缺值",
    "labeled_component_count_mismatch": "检测到编号标签但组件数量/编号不匹配，需复查原文",
    "compound_labeled_effect_needs_manual_review": "复合编号标签，需人工或大模型片段复查",
    "condition_only_component_needs_review": "仅从条件说明推断出的组件，需复查",
    "duplicate_labeled_component_values_need_review": "多个编号组件数值完全相同，可能解析错位",
    "condition_effect_mismatch_needs_review": "条件描述的效果类型与解析出的组件类型不一致，需复查",
    "attribute_branch_effect_needs_review": "同一编号内存在属性分支效果，需人工或大模型片段复查",
    "primary_labeled_effect_vu_only_needs_review": "(1) 主效果被解析成仅 VU 生效，通常是基础效果/VU追加错位",
    "vu_label_level_mismatch_needs_review": "原文说明该编号 Lv92+ 生效，但组件等级覆盖不是 VU-only",
    "blank_Lv30": "Lv30 空白但源表存在 Lv30",
    "blank_Lv50": "Lv50 空白但源表存在 Lv50",
}


def compact_report_json(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def write_html_entity_report(path: Path, lines: list[str]) -> None:
    """Write ASCII-only HTML so local viewers cannot mis-detect UTF-8."""
    text = "\n".join(lines).encode("ascii", "xmlcharrefreplace").decode("ascii")
    path.write_text(text, encoding="ascii")


def compact_report_field(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, dict) and len(value) == 1:
        return str(next(iter(value.values())))
    return compact_report_json(value)


def component_condition_report(component: dict[str, Any]) -> str:
    parts = []
    for label, key in [
        ("label", "condition_label"),
        ("role", "effect_role"),
        ("target", "target_scope"),
        ("filters", "target_filters"),
        ("trigger", "trigger_conditions"),
        ("scaling", "scaling_conditions"),
        ("availability", "availability"),
        ("activation", "activation_type"),
        ("raw", "condition_raw"),
    ]:
        text = compact_report_json(component.get(key))
        if text:
            parts.append(f"{label}: {text}")
    return "\n".join(parts)


def component_value_report(component: dict[str, Any], level: str) -> str:
    values = component.get("values_by_denko_level") or {}
    value = values.get(level)
    if not value:
        if component.get("availability", {}).get("vu_only") and level in {"30", "50"}:
            return "※VU生效"
        return ""
    return value.get("value_raw") or ""


def component_label_number(component: dict[str, Any]) -> str | None:
    label = component.get("condition_label")
    if isinstance(label, str):
        match = re.search(r"\d+", label)
        if match:
            return match.group(0)
    component_id = component.get("component_id") or ""
    match = re.search(r"_(\d+)$", component_id)
    return match.group(1) if match else None


def extract_numbered_probability(text: str, label_number: str | None) -> str:
    if not label_number:
        return text
    marker = f"({label_number})"
    start = text.find(marker)
    if start < 0:
        first_other = re.search(r"\s[\(（][1-5][\)）]", text)
        if first_other:
            return text[: first_other.start()].strip()
        return text
    remainder = text[start + len(marker) :].strip()
    for other in range(1, 6):
        if str(other) == label_number:
            continue
        next_marker = f" ({other})"
        next_index = remainder.find(next_marker)
        if next_index >= 0:
            remainder = remainder[:next_index].strip()
            break
    return remainder


def component_probability_text(component: dict[str, Any], probability: Any) -> str:
    if not probability:
        return ""
    label_number = component_label_number(component)
    if isinstance(probability, dict):
        for key, value in probability.items():
            if label_number and f"({label_number})" in str(key):
                return "" if value == "-" else str(value)
        if len(probability) == 1:
            value = str(next(iter(probability.values())))
            if label_number and "(" in value:
                return extract_numbered_probability(value, label_number)
            return value
    text = compact_report_field(probability)
    if label_number and "(" in text:
        return extract_numbered_probability(text, label_number)
    return text


def component_field_by_level_report(component: dict[str, Any], field: str) -> str:
    values = component.get("values_by_denko_level") or {}
    grouped: dict[str, list[str]] = {}
    for level in REPORT_LEVEL_ORDER:
        value = values.get(level, {}).get(field)
        text = component_probability_text(component, value) if field == "probability" else compact_report_field(value)
        if not text:
            continue
        label = "base" if level == "base" else f"Lv{level}"
        grouped.setdefault(text, []).append(label)
    if len(grouped) == 1:
        return next(iter(grouped))
    return "\n".join(f"{'/'.join(levels)}: {text}" for text, levels in grouped.items())


def component_slot_cells(component: dict[str, Any] | None) -> list[str]:
    if not component:
        return [""] * 7
    kind = compact_report_json(component.get("component_id") or component.get("effect_kind"))
    if component.get("component_id") and component.get("effect_kind") != component.get("component_id"):
        kind = f"{component.get('component_id')} ({component.get('effect_kind')})"
    return [
        kind,
        component_condition_report(component),
        component_value_report(component, "30"),
        component_value_report(component, "50") or component_value_report(component, "base"),
        component_field_by_level_report(component, "probability"),
        component_field_by_level_report(component, "duration"),
        component_field_by_level_report(component, "cooldown"),
    ]


def suspicious_rows(skill_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for skill in skill_rows:
        points = []
        labels = [component.get("condition_label") for component in skill.get("skill_components") or []]
        first_label = next((label for label in labels if label), None)
        if first_label and first_label != "(1)":
            points.append(f"首个组件编号是 {first_label}，不是 (1)，疑似排序或漏拆")
        for component in skill.get("skill_components") or []:
            reasons = [
                reason
                for reason in component.get("review_reasons") or []
                if reason in SUSPICIOUS_REASONS
            ]
            values = component.get("values_by_denko_level") or {}
            vu_only = component_has_only_vu_values(component)
            if not vu_only and values.get("30") is None and (skill.get("values_by_denko_level") or {}).get("30"):
                reasons.append("blank_Lv30")
            if not vu_only and values.get("50") is None and (skill.get("values_by_denko_level") or {}).get("50"):
                reasons.append("blank_Lv50")
            if reasons:
                reason_text = "、".join(
                    SUSPICIOUS_REASON_ZH.get(reason, reason) for reason in sorted(set(reasons))
                )
                points.append(f"{component.get('component_id')}: {reason_text}")
        if points:
            rows.append(
                {
                    "denko_id": skill.get("denko_id"),
                    "name": skill.get("name"),
                    "skill_name": skill.get("skill_name"),
                    "points": points,
                }
            )
    return rows


def component_has_only_vu_values(component: dict[str, Any]) -> bool:
    values = component.get("values_by_denko_level") or {}
    return bool(values) and set(values).issubset({"92", "96", "100"})


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
    suspicious = suspicious_rows(skill_rows)

    lines = [
        "<!doctype html>",
        '<html lang="zh-CN">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>Original {start}-{end} Ingestion Review</title>",
        "<style>body{font-family:system-ui,sans-serif;line-height:1.5;margin:24px}table{border-collapse:collapse;width:100%;margin:12px 0 24px}th,td{border:1px solid #ccc;padding:6px 8px;vertical-align:top}th{background:#f5f5f5}code{background:#f6f8fa;padding:1px 4px}.table-scroll{overflow-x:auto}.component-table{font-size:12px;min-width:1800px}.component-table th,.component-table td{white-space:pre-wrap;min-width:90px;max-width:300px}.component-table .condition-col{min-width:260px;max-width:380px}.component-table .value-col{min-width:150px;max-width:240px}</style>",
        "</head><body>",
        f"<h1>Original {start}-{end} 数据读取报告</h1>",
        "<p>controller-first 执行：本批只使用脚本、缓存与确定性 parser；未调用 LLM。</p>",
        "<h2>批次指标</h2>",
        "<table><tbody>",
        f"<tr><th>范围</th><td>original:{start:03d} - original:{end:03d}</td></tr>",
        f"<tr><th>record_count</th><td>{len(denko_rows)}</td></tr>",
        f"<tr><th>batch_size</th><td>{batch_size}</td></tr>",
        f"<tr><th>review_queue</th><td>{len(reviews)}</td></tr>",
        f"<tr><th>suspicious_items</th><td>{len(suspicious)}</td></tr>",
        f"<tr><th>classification</th><td>{esc(dict(classification))}</td></tr>",
        f"<tr><th>review_reasons</th><td>{esc(dict(reason_counts))}</td></tr>",
        f"<tr><th>component_kinds</th><td>{esc(dict(component_counts))}</td></tr>",
        "</tbody></table>",
    ]

    lines.append("<h2>可疑项优先</h2>")
    if suspicious:
        lines.append("<table><thead><tr><th>denko_id</th><th>name</th><th>skill</th><th>可疑点</th></tr></thead><tbody>")
        for row in suspicious:
            lines.append(
                "<tr>"
                f"<td>{esc(row['denko_id'])}</td>"
                f"<td>{esc(row['name'])}</td>"
                f"<td>{esc(row['skill_name'])}</td>"
                f"<td>{esc(' / '.join(row['points']))}</td>"
                "</tr>"
            )
        lines.append("</tbody></table>")
    else:
        lines.append("<p>本批未检测到高优先级可疑项。</p>")

    lines.append("<h2>分批复盘</h2>")
    for batch in batch_slices(denko_rows, batch_size):
        batch_ids = [row["identity"]["denko_id"] for row in batch]
        batch_skills = [by_id[denko_id] for denko_id in batch_ids if denko_id in by_id]
        batch_classification = Counter(classify_skill_row(row) for row in batch_skills)
        lines.append(
            f"<p><strong>{esc(batch_ids[0])} - {esc(batch_ids[-1])}</strong>: "
            f"{len(batch)} records, {esc(dict(batch_classification))}</p>"
        )

    lines.append("<h2>技能分量表</h2>")
    lines.append("<p>一行表示一个已识别的技能分量；不再展开空 skill slot。概率列按当前分量的 (1)/(2)/(3) label 单独显示。</p>")
    headers = [
        "denko_id",
        "name",
        "type",
        "attribute",
        "color",
        "skill",
        "component",
        "label",
        "role",
        "kind",
        "target",
        "condition",
        "Lv30内容",
        "Lv50内容",
        "Lv92内容",
        "Lv96内容",
        "Lv100内容",
        "probability",
        "duration",
        "CD",
        "review_reasons",
    ]
    header_cells = []
    for header in headers:
        css_class = ' class="condition-col"' if header == "condition" else ' class="value-col"' if header in {"Lv30内容", "Lv50内容", "Lv92内容", "Lv96内容", "Lv100内容", "probability"} else ""
        header_cells.append(f"<th{css_class}>{esc(header)}</th>")
    lines.append('<div class="table-scroll">')
    lines.append(f'<table class="component-table"><thead><tr>{"".join(header_cells)}</tr></thead><tbody>')
    for denko in denko_rows:
        ident = denko["identity"]
        skill = by_id.get(ident["denko_id"], {})
        components = list(skill.get("skill_components") or [])
        if not components:
            components = [None]
        for component in components:
            kind = ""
            if component:
                kind = compact_report_json(component.get("component_id") or component.get("effect_kind"))
                if component.get("component_id") and component.get("effect_kind") != component.get("component_id"):
                    kind = f"{component.get('component_id')} ({component.get('effect_kind')})"
            lines.append(
                "<tr>"
                f"<td>{esc(ident['denko_id'])}</td>"
                f"<td>{esc(ident['name'])}</td>"
                f"<td>{esc(ident.get('type'))}</td>"
                f"<td>{esc(ident.get('attribute'))}</td>"
                f"<td>{esc(ident.get('color'))}</td>"
                f"<td>{esc(skill.get('skill_name'))}</td>"
                f"<td>{esc(kind)}</td>"
                f"<td>{esc(component.get('condition_label') if component else '')}</td>"
                f"<td>{esc(component.get('effect_role') if component else '')}</td>"
                f"<td>{esc(component.get('effect_kind') if component else '')}</td>"
                f"<td>{esc(compact_report_json(component.get('target_scope')) if component else '')}</td>"
                f"<td>{esc(component_condition_report(component) if component else '')}</td>"
                f"<td>{esc(component_value_report(component, '30') if component else '')}</td>"
                f"<td>{esc((component_value_report(component, '50') or component_value_report(component, 'base')) if component else '')}</td>"
                f"<td>{esc(component_value_report(component, '92') if component else '')}</td>"
                f"<td>{esc(component_value_report(component, '96') if component else '')}</td>"
                f"<td>{esc(component_value_report(component, '100') if component else '')}</td>"
                f"<td>{esc(component_field_by_level_report(component, 'probability') if component else '')}</td>"
                f"<td>{esc(component_field_by_level_report(component, 'duration') if component else '')}</td>"
                f"<td>{esc(component_field_by_level_report(component, 'cooldown') if component else '')}</td>"
                f"<td>{esc(component.get('review_reasons') if component else skill.get('record_meta', {}).get('review_reasons'))}</td>"
                "</tr>"
            )
    lines.extend(
        [
            "</tbody></table></div>",
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
    write_html_entity_report(path, lines)
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
