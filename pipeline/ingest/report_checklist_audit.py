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
import review_cycle_controller as controller


BATCH_RE = re.compile(r"(?P<pool>original|extra)_(?P<start>\d{3})_(?P<end>\d{3})_skill_facts\.jsonl$")
REPORT_RE = re.compile(r"(?P<pool>original|extra)_(?P<start>\d{3})_(?P<end>\d{3})_batch_review_zh\.html$")
VU_LEVELS = {"92", "96", "100"}
BLOCKING_REASONS = controller.BLOCKING_REASONS
MOJIBAKE_PATTERNS = ("????", "HP?30%", "锛", "閵", "閻", "繝", "縺", "蜀咏悄")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def batch_key(path: Path) -> str | None:
    match = BATCH_RE.fullmatch(path.name)
    if not match:
        return None
    return f"{match.group('pool')}_{match.group('start')}_{match.group('end')}"


def report_key(path: Path) -> str | None:
    match = REPORT_RE.fullmatch(path.name)
    if not match:
        return None
    return f"{match.group('pool')}_{match.group('start')}_{match.group('end')}"


def label_number(component: dict[str, Any]) -> str | None:
    label = component.get("condition_label")
    if isinstance(label, str):
        match = re.search(r"\d+", label)
        if match:
            return match.group(0)
    component_id = component.get("component_id") or ""
    match = re.search(r"_(\d+)$", component_id)
    return match.group(1) if match else None


def has_labeled_text(value: Any, min_count: int = 2) -> bool:
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    labels = set(re.findall(r"[\(\uff08](\d+)[\)\uff09]", text))
    return len(labels) >= min_count


def has_mixed_labeled_probability_text(text: str) -> bool:
    for match in re.finditer(r"発動率[^；;、,，]*", text):
        labels = set(re.findall(r"[\(\uff08](\d+)[\)\uff09]", match.group(0)))
        if len(labels) >= 2:
            return True
    return False


def source_has_level(row: dict[str, Any], level: str) -> bool:
    return bool((row.get("values_by_denko_level") or {}).get(level))


def component_levels(component: dict[str, Any]) -> set[str]:
    return set((component.get("values_by_denko_level") or {}).keys())


def is_vu_only(component: dict[str, Any]) -> bool:
    return bool((component.get("availability") or {}).get("vu_only"))


def component_text(component: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("condition_raw", "remarks_raw", "effect_kind", "target_scope"):
        value = component.get(key)
        if value:
            parts.append(str(value))
    for value in (component.get("values_by_denko_level") or {}).values():
        for key in ("value_raw", "source_text"):
            if value.get(key):
                parts.append(str(value[key]))
    return " / ".join(parts)


def add_issue(
    issues: list[dict[str, Any]],
    batch: str,
    denko_id: str | None,
    name: str | None,
    severity: str,
    category: str,
    issue: str,
    detail_zh: str,
    component_id: str | None = None,
    fix_hint_zh: str | None = None,
    evidence: Any = None,
) -> None:
    issues.append(
        {
            "batch": batch,
            "denko_id": denko_id,
            "name": name,
            "component_id": component_id,
            "severity": severity,
            "category": category,
            "issue": issue,
            "detail_zh": detail_zh,
            "fix_hint_zh": fix_hint_zh,
            "evidence": evidence,
        }
    )


def audit_report(batch: str, path: Path, issues: list[dict[str, Any]]) -> dict[str, Any]:
    raw = path.read_bytes()
    ascii_only = all(byte < 128 for byte in raw)
    text = path.read_text(encoding="ascii" if ascii_only else "utf-8", errors="replace")
    rendered = html.unescape(text)
    mojibake_hits = {pattern: rendered.count(pattern) for pattern in MOJIBAKE_PATTERNS if rendered.count(pattern)}
    checks = {
        "ascii_only": ascii_only,
        "has_component_table": "技能分量表" in rendered,
        "has_vu_columns": all(col in rendered for col in ("Lv92内容", "Lv96内容", "Lv100内容")),
        "has_old_slot_matrix": "skill1_kind" in rendered or "skill1_condition" in rendered,
        "double_question_count": rendered.count("??"),
        "mojibake_hits": mojibake_hits,
    }
    if not ascii_only:
        add_issue(issues, batch, None, None, "medium", "report_encoding", "report_not_ascii_entity", "HTML 报告不是 ASCII entity 输出，本地查看时容易再次被编码误导。", fix_hint_zh="用项目的 HTML entity 写入函数重生成报告。")
    if not checks["has_component_table"]:
        add_issue(issues, batch, None, None, "high", "report_structure", "component_table_missing", "报告缺少一行一个 component 的技能分量表。", fix_hint_zh="重生成报告，或修正 write_html_report。")
    if not checks["has_vu_columns"]:
        add_issue(issues, batch, None, None, "high", "report_structure", "vu_columns_missing", "报告缺少 Lv92/Lv96/Lv100 内容列，VU-only 技能容易被误判为空白。", fix_hint_zh="报告表格需要保留 VU 三列。")
    if checks["has_old_slot_matrix"]:
        add_issue(issues, batch, None, None, "high", "report_structure", "old_5_slot_matrix", "报告仍包含旧 skill1_* 固定槽矩阵，容易产生空白 slot 误读。", fix_hint_zh="改为 component 长表。")
    if checks["double_question_count"] or checks["mojibake_hits"]:
        add_issue(issues, batch, None, None, "critical", "encoding", "mojibake_or_question_damage", "报告中存在疑似乱码或问号替换损坏。", evidence=checks, fix_hint_zh="先用 UTF-8 JSONL/raw 复查；坏数据必须重跑或重写 patch。")
    return checks


def audit_skill_row(batch: str, row: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    denko_id = row.get("denko_id")
    name = row.get("name")
    components = row.get("skill_components") or []
    labels = [component.get("condition_label") for component in components]
    first_label = next((label for label in labels if label), None)
    if first_label and first_label != "(1)":
        add_issue(issues, batch, denko_id, name, "high", "label", "first_label_not_1", "第一个带编号 component 不是 (1)，疑似主效果漏抓或排序错位。", evidence=labels, fix_hint_zh="复查条件表，补齐 (1) 或重排 component。")
    if has_mixed_labeled_probability_text(row.get("summary_zh") or ""):
        add_issue(issues, batch, denko_id, name, "medium", "summary", "summary_mixed_labeled_probability", "summary_zh 里仍混有多个编号效果/概率，可能没有复用 component 级拆分结果。", evidence=(row.get("summary_zh") or "")[:300], fix_hint_zh="重建 summary_zh，并按 component label 过滤概率。")

    signatures: Counter[str] = Counter()
    for component in components:
        signatures[
            json.dumps(
                {
                    "label": component.get("condition_label"),
                    "kind": component.get("effect_kind"),
                    "target": component.get("target_scope"),
                    "condition": component.get("condition_raw"),
                    "values": component.get("values_by_denko_level"),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        ] += 1
    for _signature, count in signatures.items():
        if count > 1:
            add_issue(issues, batch, denko_id, name, "medium", "component", "duplicate_component_signature", "同一 denko 内存在完全相同的 component，疑似复制或拆分错位。", evidence={"count": count}, fix_hint_zh="用原文片段复查是否应合并、删除或重拆。")

    for component in components:
        component_id = component.get("component_id")
        label_num = label_number(component)
        component_id_num = None
        match = re.search(r"_(\d+)$", component_id or "")
        if match:
            component_id_num = match.group(1)
        if label_num and component_id_num and label_num != component_id_num:
            add_issue(issues, batch, denko_id, name, "high", "label", "label_component_id_mismatch", "condition_label 与 component_id 编号不一致。", component_id, fix_hint_zh="重命名或重建 component。", evidence={"label": component.get("condition_label"), "component_id": component_id})

        levels = component_levels(component)
        if label_num == "1" and levels and levels.issubset(VU_LEVELS) and not is_vu_only(component):
            add_issue(issues, batch, denko_id, name, "high", "vu", "primary_label_only_vu", "(1) 主效果只有 VU 等级，通常说明基础效果漏抓。", component_id, fix_hint_zh="复查 Lv30/Lv50 和条件表。")
        if not is_vu_only(component):
            for level in ("30", "50"):
                if source_has_level(row, level) and level not in levels:
                    add_issue(issues, batch, denko_id, name, "high", "level", f"non_vu_missing_lv{level}", f"非 VU component 缺 Lv{level}。", component_id, fix_hint_zh="复查技能等级表，或确认该 component 应标为 vu_only。")

        for level, value in (component.get("values_by_denko_level") or {}).items():
            probability = value.get("probability")
            if isinstance(probability, dict) and has_labeled_text(probability):
                add_issue(issues, batch, denko_id, name, "high", "probability", "mixed_labeled_probability", "probability 中仍混有多个 label。", component_id, evidence={"level": level, "probability": probability}, fix_hint_zh="按 component label 拆成独立 activation_probability。")
            value_raw = value.get("value_raw")
            if isinstance(value_raw, str) and label_num == "1" and "(2)" in value_raw:
                add_issue(issues, batch, denko_id, name, "high", "value", "base_value_contains_label_2", "(1) component 的 value_raw 中仍包含 (2)。", component_id, evidence={"level": level, "value_raw": value_raw}, fix_hint_zh="按 label 切分 value_raw。")

        blockers = sorted(set(component.get("review_reasons") or []) & BLOCKING_REASONS)
        if blockers:
            add_issue(issues, batch, denko_id, name, "high", "blocking_reason", "component_has_blocking_reason", "component 仍带阻塞级 review reason。", component_id, evidence=blockers, fix_hint_zh="优先判断是否是共性 parser rule；无法共性化再走语义 patch。")
        if component_id and component_id.startswith("component_"):
            add_issue(issues, batch, denko_id, name, "medium", "fallback", "fallback_component", "出现 fallback component，语义不稳定。", component_id, fix_hint_zh="复查原文并替换为语义 effect_kind。")



def audit_pool(pool: str) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    report_checks: dict[str, Any] = {}
    for report_path in sorted(base.REPORT_DIR.glob(f"{pool}_*_batch_review_zh.html")):
        key = report_key(report_path)
        if key:
            report_checks[key] = audit_report(key, report_path, issues)
    skill_file_count = 0
    skill_record_count = 0
    for skill_path in sorted(base.RECORD_DIR.glob(f"{pool}_*_skill_facts.jsonl")):
        key = batch_key(skill_path)
        if not key:
            continue
        skill_file_count += 1
        rows = read_jsonl(skill_path)
        skill_record_count += len(rows)
        for row in rows:
            audit_skill_row(key, row, issues)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(base.JST).isoformat(),
        "scope": pool,
        "metrics": {
            "issue_count": len(issues),
            "skill_file_count": skill_file_count,
            "skill_record_count": skill_record_count,
            "severity_counts": dict(Counter(issue["severity"] for issue in issues)),
            "category_counts": dict(Counter(issue["category"] for issue in issues)),
        },
        "report_checks": report_checks,
        "issues": issues,
    }


def write_markdown(path: Path, audit: dict[str, Any]) -> None:
    issues = audit.get("issues") or []
    lines = [
        f"# {audit.get('scope')} 全量报告校对审计",
        "",
        f"- generated_at: `{audit.get('generated_at')}`",
        f"- issue_count: `{audit.get('metrics', {}).get('issue_count')}`",
        f"- skill_records: `{audit.get('metrics', {}).get('skill_record_count')}`",
        f"- severity_counts: `{audit.get('metrics', {}).get('severity_counts')}`",
        f"- category_counts: `{audit.get('metrics', {}).get('category_counts')}`",
        "",
    ]
    if issues:
        lines.extend(["## 可疑项目", ""])
        lines.append("| severity | batch | denko | component | issue | 理由 |")
        lines.append("|---|---|---|---|---|---|")
        for issue in issues:
            denko = " ".join(part for part in [issue.get("denko_id"), issue.get("name")] if part)
            lines.append(
                f"| {issue.get('severity')} | {issue.get('batch')} | {denko} | {issue.get('component_id') or ''} | {issue.get('issue')} | {issue.get('detail_zh')} |"
            )
    else:
        lines.append("按当前 checklist，未检出剩余 issue。")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def default_json_out(pool: str) -> Path:
    suffix = "001_163" if pool == "original" else "full"
    return base.ROOT / "data" / "agent_runs" / f"{pool}_{suffix}_report_checklist_audit.json"


def default_md_out(pool: str) -> Path:
    suffix = "001_163" if pool == "original" else "full"
    return base.ROOT / "data" / "agent_runs" / f"{pool}_{suffix}_report_checklist_audit_zh.md"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", choices=sorted(base.LIST_PAGES), default="original")
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--md-out", type=Path)
    args = parser.parse_args()
    audit = audit_pool(args.pool)
    json_out = args.json_out or default_json_out(args.pool)
    md_out = args.md_out or default_md_out(args.pool)
    write_json(json_out, audit)
    write_markdown(md_out, audit)
    print(json.dumps({"issue_count": audit["metrics"]["issue_count"], "json": str(json_out), "md": str(md_out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
