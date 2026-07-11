from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[2]
STEP1_SKILLS = ROOT / "data" / "step1_db" / "skill_facts.jsonl"
PROTOTYPE_INDEX = ROOT / "data" / "prototype_db" / "prototype_index.json"
PROTOTYPE_RECORDS = ROOT / "data" / "prototype_db" / "prototype_records.jsonl"
PROTOTYPE_REPORT = ROOT / "data" / "reports" / "step2_prototype_lookup_zh.html"
REPORTS = {
    "attack": ROOT / "data" / "reports" / "step2_attack_support_rankings_zh.html",
    "exp_pt": ROOT / "data" / "reports" / "step2_exp_pt_support_rankings_zh.html",
    "defense": ROOT / "data" / "reports" / "step2_defense_support_rankings_zh.html",
    "utility": ROOT / "data" / "reports" / "step2_skill_utility_reports_zh.html",
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
UTILITY_EFFECT_LABELS = {
    "nullification_passive": {"技能无效化", "技能效果量无效化", "技能强制结束", "伤害无效化", "バッテリー不可"},
    "nullification_active": {"技能无效化", "技能效果量无效化", "技能强制结束", "伤害无效化", "バッテリー不可"},
    "skill_effect_boost": {"技能效果量强化"},
    "accessory_effect_boost": {"饰品效果量强化"},
    "film_effect_boost": {"皮肤效果量强化"},
    "cooldown_probability": {"发动率强化", "CD缩短", "CD解除"},
    "event_access": {"追加访问", "思い出し访问次数增加", "随机访问已访问站", "远程访问"},
    "access_range": {"雷达探测范围", "雷达最大探测范围"},
}
EXPECTED_LEVEL_OPTIONS = ["50", "30", "80", "92", "96", "100"]

MISSING_WORD_PATTERNS = {
    "blank_type_subject": re.compile(r"編成内の\s+が|編成内の\s+の"),
    "blank_attribute_subject": re.compile(r"すべてのでんこが\s+(?:効果|/|$)|全て\s+で"),
    "blank_formation_pair": re.compile(r"と\s+のみの編成"),
    "blank_opponent_if": re.compile(r"相手が\s+なら"),
    "blank_station_access": re.compile(r"駅で\s+にアクセス"),
    "split_attribute_denko": re.compile(r"属性\s+でんこ"),
    "trailing_target_fragment": re.compile(r"DEF増加\s+(?:自身の|編成内の)\b"),
    "leading_cross_reference_fragment": re.compile(r"^(?:の|が|に追加|で(?=スコア))"),
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


def structural_audit(name: str, path: Path, canonical_ids: set[str]) -> dict[str, Any]:
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    issues: list[dict[str, Any]] = []
    buttons = {button.get("data-tab"): cell_text(button) for button in soup.select(".tab-button[data-tab]")}
    panels = {panel.get("data-tab-panel"): panel for panel in soup.select("[data-tab-panel]")}
    level_options = [str(option.get("value") or "") for option in soup.select("#levelMode option")]
    if level_options != EXPECTED_LEVEL_OPTIONS:
        issues.append(
            {
                "category": "level_selector_mismatch",
                "expected": EXPECTED_LEVEL_OPTIONS,
                "actual": level_options,
            }
        )
    if set(buttons) != set(panels):
        issues.append({"category": "tab_panel_mismatch", "buttons": sorted(buttons), "panels": sorted(panels)})
    row_count = 0
    for tab_id, panel in panels.items():
        rows = panel.select("tbody tr")
        row_count += len(rows)
        visible = sum(row.get("data-vu-only") != "true" for row in rows)
        vu_only = sum(row.get("data-vu-only") == "true" for row in rows)
        label = buttons.get(tab_id, "")
        count_match = re.search(r"(\d+)(?:\s*\+(\d+)\s*VU)?$", label)
        if not count_match or int(count_match.group(1)) != visible or int(count_match.group(2) or 0) != vu_only:
            issues.append({"category": "tab_count_mismatch", "tab": tab_id, "label": label, "visible": visible, "vu_only": vu_only})
        headers = header_map(panel.select_one("table")) if panel.select_one("table") else {}
        for row in rows:
            cells = [cell_text(td) for td in row.select("td")]
            denko_cell = cells[headers.get("でんこ", 1)] if len(cells) > 1 else ""
            denko_match = re.match(r"([a-z]+:\d+)", denko_cell)
            if not denko_match or denko_match.group(1) not in canonical_ids:
                issues.append({"category": "unknown_denko", "tab": tab_id, "denko": denko_cell})
            try:
                level_data = json.loads(row.get("data-levels") or "{}")
            except json.JSONDecodeError:
                issues.append({"category": "invalid_level_json", "tab": tab_id, "denko": denko_cell})
                level_data = {}
            if "92" in level_data and "100" in level_data and "96" not in level_data:
                issues.append({"category": "missing_lv96_between_vu_levels", "tab": tab_id, "denko": denko_cell})
            if name == "utility" and tab_id in UTILITY_EFFECT_LABELS:
                effect = cells[headers.get("效果", 4)].split(" 效果分支", 1)[0]
                if effect not in UTILITY_EFFECT_LABELS[tab_id]:
                    issues.append({"category": "utility_category_boundary", "tab": tab_id, "denko": denko_cell, "effect": effect})
    return {"report": name, "row_count": row_count, "tab_count": len(panels), "issue_count": len(issues), "issues": issues}


def prototype_audit() -> dict[str, Any]:
    index = json.loads(PROTOTYPE_INDEX.read_text(encoding="utf-8"))
    record_count = sum(1 for line in PROTOTYPE_RECORDS.read_text(encoding="utf-8").splitlines() if line.strip())
    soup = BeautifulSoup(PROTOTYPE_REPORT.read_text(encoding="utf-8"), "html.parser")
    checks = {
        "record_count_matches_index": record_count == index.get("audit", {}).get("counts", {}).get("records"),
        "all_records_rendered": len(soup.select(".character-card")) == record_count,
        "all_records_have_source_badge": len(soup.select("a.source-badge")) == record_count,
        "prompt_errors_empty": not index.get("prompt_errors"),
        "six_public_groups_present": len(index.get("groups") or {}) == 6,
    }
    return {
        "record_count": record_count,
        "character_cards": len(soup.select(".character-card")),
        "directory_items": len(soup.select("[data-directory-item]")),
        "known_missing_prefecture": len(index.get("audit", {}).get("missing_prefecture") or []),
        "checks": checks,
        "issue_count": sum(not passed for passed in checks.values()),
    }


def db_semantic_audit() -> dict[str, Any]:
    rows = [json.loads(line) for line in STEP1_SKILLS.read_text(encoding="utf-8").splitlines() if line.strip()]
    issues: list[dict[str, Any]] = []
    by_id = {str(row.get("denko_id")): row for row in rows}
    for row in rows:
        components = row.get("skill_components") or []
        kinds_by_label: dict[str, set[str]] = {}
        for component in components:
            label = str(component.get("condition_label") or "")
            kinds_by_label.setdefault(label, set()).add(str(component.get("effect_kind") or ""))
        for component in components:
            value_text = " ".join(
                str(value.get("value_raw") or "")
                for value in (component.get("values_by_denko_level") or {}).values()
            )
            label_kinds = kinds_by_label.get(str(component.get("condition_label") or ""), set())
            has_split_pair = bool(label_kinds & {"exp_gain"}) and bool(
                label_kinds & {"score_gain", "additional_score_gain"}
            )
            if "経験値" in value_text and "スコア" in value_text and not has_split_pair:
                issues.append(
                    {
                        "category": "compound_effect_unsplit",
                        "denko_id": row.get("denko_id"),
                        "component_id": component.get("component_id"),
                        "effect_kind": component.get("effect_kind"),
                    }
                )
            if component.get("effect_kind") == "reboot" and any(marker in value_text for marker in ("経験値", "スコア")):
                issues.append(
                    {
                        "category": "effect_kind_value_mismatch",
                        "denko_id": row.get("denko_id"),
                        "component_id": component.get("component_id"),
                        "effect_kind": "reboot",
                    }
                )
            if component.get("effect_kind") in {"score_gain", "additional_score_gain", "score_random_modifier", "match_bonus"}:
                if component.get("target_scope") not in (["master"], ["master_account"]):
                    issues.append(
                        {
                            "category": "score_recipient_not_master",
                            "denko_id": row.get("denko_id"),
                            "component_id": component.get("component_id"),
                            "target_scope": component.get("target_scope"),
                        }
                    )

    lenya = by_id.get("extra:041") or {}
    lenya_components = {str(component.get("component_id")): component for component in lenya.get("skill_components") or []}
    expected_lenya = {
        "exp_gain_1": ("exp_gain", ["accessed_denko"]),
        "score_gain": ("score_gain", ["master"]),
        "exp_gain_2": ("exp_gain", ["accessed_denko"]),
        "score_gain_2": ("additional_score_gain", ["master"]),
    }
    for component_id, (effect_kind, target_scope) in expected_lenya.items():
        component = lenya_components.get(component_id)
        if not component or component.get("effect_kind") != effect_kind or component.get("target_scope") != target_scope:
            issues.append(
                {
                    "category": "lenya_exp_score_split_regression",
                    "denko_id": "extra:041",
                    "component_id": component_id,
                    "expected_effect_kind": effect_kind,
                    "expected_target_scope": target_scope,
                }
            )
    if "reboot_2" in lenya_components:
        issues.append(
            {
                "category": "lenya_exp_score_split_regression",
                "denko_id": "extra:041",
                "component_id": "reboot_2",
                "reason": "VU additional EXP/score must not remain classified as reboot",
            }
        )
    counts = Counter(issue["category"] for issue in issues)
    return {"issue_count": len(issues), "category_counts": dict(sorted(counts.items())), "issues": issues}


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
    lines.extend(["## 结构与分类边界", ""])
    for item in result.get("structural_audits") or []:
        lines.append(
            f"- {item['report']}: rows `{item['row_count']}`, tabs `{item['tab_count']}`, issues `{item['issue_count']}`"
        )
        for issue in item["issues"]:
            lines.append(f"  - `{issue['category']}`: `{json.dumps(issue, ensure_ascii=False)}`")
    prototype = result.get("prototype_audit") or {}
    lines.extend(
        [
            "",
            "## 原型反查",
            "",
            f"- records/cards: `{prototype.get('record_count')}/{prototype.get('character_cards')}`",
            f"- directory_items: `{prototype.get('directory_items')}`",
            f"- known_missing_prefecture: `{prototype.get('known_missing_prefecture')}`",
            f"- issue_count: `{prototype.get('issue_count')}`",
            "",
        ]
    )
    db_semantic = result.get("db_semantic_audit") or {}
    lines.extend(
        [
            "## Step1 DB 语义回归",
            "",
            f"- issue_count: `{db_semantic.get('issue_count')}`",
            f"- category_counts: `{db_semantic.get('category_counts')}`",
            "",
        ]
    )
    for issue in db_semantic.get("issues") or []:
        lines.append(f"- `{json.dumps(issue, ensure_ascii=False)}`")
    if db_semantic.get("issues"):
        lines.append("")
    OUT_MD.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    reports = [audit_report(name, path) for name, path in REPORTS.items()]
    canonical_ids = {
        str(json.loads(line).get("denko_id"))
        for line in STEP1_SKILLS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    structural = [structural_audit(name, path, canonical_ids) for name, path in REPORTS.items()]
    prototype = prototype_audit()
    db_semantic = db_semantic_audit()
    total_counts = Counter()
    for report in reports:
        total_counts.update(report["category_counts"])
    result = {
        "reports": reports,
        "structural_audits": structural,
        "prototype_audit": prototype,
        "db_semantic_audit": db_semantic,
        "total_issue_rows": sum(report["row_issue_count"] for report in reports),
        "category_counts": dict(sorted(total_counts.items())),
        "issue_count": sum(report["row_issue_count"] for report in reports)
        + sum(item["issue_count"] for item in structural)
        + prototype["issue_count"]
        + db_semantic["issue_count"],
    }
    OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
    write_markdown(result)
    print(json.dumps({"json": str(OUT_JSON.relative_to(ROOT)), "md": str(OUT_MD.relative_to(ROOT)), "total_issue_rows": result["total_issue_rows"], "category_counts": result["category_counts"], "issue_count": result["issue_count"]}, ensure_ascii=False))
    if result["issue_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
