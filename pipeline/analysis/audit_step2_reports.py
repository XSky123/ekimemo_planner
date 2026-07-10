from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[2]
REPORTS = {
    "attack": ROOT / "data" / "reports" / "step2_attack_support_rankings_zh.html",
    "exp_pt": ROOT / "data" / "reports" / "step2_exp_pt_support_rankings_zh.html",
    "defense": ROOT / "data" / "reports" / "step2_defense_support_rankings_zh.html",
    "mobility": ROOT / "data" / "reports" / "step2_mobility_visit_rankings_zh.html",
}
OUT_JSON = ROOT / "data" / "audits" / "step2_semantic_audit.json"
OUT_MD = ROOT / "data" / "audits" / "step2_semantic_audit_zh.md"


UNKNOWN_TARGET_TOKENS = {"对象未明", "対象未明"}
INTERNAL_KEY_TOKENS = {
    "activation_probability",
    "score_increase_probability",
    "score_decrease_probability",
    "value_numeric",
    "target_scope",
}
AMBIGUOUS_VALUE_TOKENS = {"数值未明", "条件型", "条件型/数值未明"}
MOJIBAKE_TOKENS = {"????", "\ufffd"}

MISSING_WORD_PATTERNS = {
    "blank_type_subject": re.compile(r"編成内の\s+が|編成内の\s+の"),
    "blank_attribute_subject": re.compile(r"すべてのでんこが\s+(?:効果|/|$)|全て\s+で"),
    "blank_formation_pair": re.compile(r"と\s+のみの編成"),
    "blank_opponent_if": re.compile(r"相手が\s+なら"),
    "blank_station_access": re.compile(r"駅で\s+にアクセス"),
    "split_attribute_denko": re.compile(r"属性\s+でんこ"),
    "trailing_target_fragment": re.compile(r"DEF増加\s+(?:自身の|編成内の)\b"),
}


def cell_text(cell: Any) -> str:
    return " ".join(cell.get_text(" ", strip=True).split())


def header_map(table: Any) -> dict[str, int]:
    headers = [cell_text(th) for th in table.select("thead th")]
    return {header: index for index, header in enumerate(headers)}


def row_issue_flags(cells: list[str], header_index: dict[str, int]) -> list[dict[str, str]]:
    joined = " | ".join(cells)
    condition = cells[header_index.get("触发与条件", len(cells) - 1)] if cells else ""
    target = cells[header_index.get("对象/限制", -1)] if header_index.get("对象/限制", -1) < len(cells) else ""
    max_value = cells[header_index.get("理论最大", header_index.get("理论值", -1))] if cells else ""
    avg_value = cells[header_index.get("平均值", header_index.get("期望值", header_index.get("粗略期望", -1)))] if cells else ""
    effect = cells[header_index.get("效果", -1)] if header_index.get("效果", -1) < len(cells) else ""
    flags: list[dict[str, str]] = []

    for token in UNKNOWN_TARGET_TOKENS:
        if token in target or token in joined:
            flags.append({"category": "unknown_target", "reason": f"对象列仍出现 {token}"})
            break

    for token in INTERNAL_KEY_TOKENS:
        if token in joined:
            flags.append({"category": "internal_key", "reason": f"展示层泄漏内部 key: {token}"})
            break

    for token in MOJIBAKE_TOKENS:
        if token in joined:
            flags.append({"category": "mojibake", "reason": "展示层疑似乱码或替换字符"})
            break

    for name, pattern in MISSING_WORD_PATTERNS.items():
        if pattern.search(condition):
            flags.append({"category": "missing_word", "reason": f"条件文字疑似合并单元格缺词: {name}"})

    if any(token in max_value or token in avg_value or token in effect for token in AMBIGUOUS_VALUE_TOKENS):
        flags.append({"category": "ambiguous_value", "reason": "数值列/效果列仍是条件型或数值未明"})

    if "?%" in joined:
        flags.append({"category": "ambiguous_value", "reason": "展示层仍含未清洗的 ?% 概率或数值"})

    return flags


def audit_report(name: str, path: Path) -> dict[str, Any]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    rows: list[dict[str, Any]] = []
    for table in soup.select("table"):
        hmap = header_map(table)
        if not hmap:
            continue
        for tr in table.select("tbody tr"):
            cells = [cell_text(td) for td in tr.select("td")]
            if not cells:
                continue
            flags = row_issue_flags(cells, hmap)
            if not flags:
                continue
            rows.append(
                {
                    "report": name,
                    "denko": cells[hmap.get("でんこ", 1)] if len(cells) > 1 else "",
                    "effect": cells[hmap.get("效果", 4)] if len(cells) > 4 else "",
                    "target_filters": cells[hmap.get("对象/限制", 12)] if len(cells) > 12 else "",
                    "condition": cells[hmap.get("触发与条件", len(cells) - 1)] if cells else "",
                    "flags": flags,
                }
            )
    counts = Counter(flag["category"] for row in rows for flag in row["flags"])
    return {
        "report": name,
        "path": str(path.relative_to(ROOT)),
        "row_issue_count": len(rows),
        "category_counts": dict(sorted(counts.items())),
        "issues": rows,
    }


def write_markdown(result: dict[str, Any]) -> None:
    lines = [
        "# Step2 报表全量语义审计",
        "",
        f"- total_issue_rows: `{result['total_issue_rows']}`",
        f"- category_counts: `{result['category_counts']}`",
        "",
    ]
    for report in result["reports"]:
        lines.extend(
            [
                f"## {report['report']}",
                "",
                f"- path: `{report['path']}`",
                f"- issue_rows: `{report['row_issue_count']}`",
                f"- category_counts: `{report['category_counts']}`",
                "",
            ]
        )
        if not report["issues"]:
            lines.append("无问题。")
            lines.append("")
            continue
        lines.extend(["| denko | effect | categories | reason | target/condition |", "|---|---|---|---|---|"])
        for issue in report["issues"]:
            categories = ", ".join(flag["category"] for flag in issue["flags"])
            reasons = "<br>".join(flag["reason"] for flag in issue["flags"])
            target_condition = f"{issue['target_filters']}<br>{issue['condition']}"
            lines.append(
                "| "
                + " | ".join(
                    item.replace("|", "\\|")
                    for item in [
                        issue["denko"],
                        issue["effect"],
                        categories,
                        reasons,
                        target_condition,
                    ]
                )
                + " |"
            )
        lines.append("")
    OUT_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    reports = [audit_report(name, path) for name, path in REPORTS.items()]
    total_counts = Counter()
    for report in reports:
        total_counts.update(report["category_counts"])
    result = {
        "reports": reports,
        "total_issue_rows": sum(report["row_issue_count"] for report in reports),
        "category_counts": dict(sorted(total_counts.items())),
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    write_markdown(result)
    print(json.dumps({"json": str(OUT_JSON.relative_to(ROOT)), "md": str(OUT_MD.relative_to(ROOT)), "total_issue_rows": result["total_issue_rows"], "category_counts": result["category_counts"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
