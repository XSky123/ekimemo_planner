from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import parse as base
import review_cycle_controller as controller


BATCH_RE = re.compile(r"original_(\d{3})_(\d{3})_skill_facts\.jsonl$")
REPORT_RE = re.compile(r"original_(\d{3})_(\d{3})_batch_review_zh\.html$")
LEVEL_ORDER = ("1", "5", "15", "30", "50", "60", "70", "80", "92", "96", "100")
VU_LEVELS = {"92", "96", "100"}
BLOCKING_REASONS = controller.BLOCKING_REASONS
MOJIBAKE_PATTERNS = ("????", "HP?30%", "銇", "銈", "鐧", "鍔", "鏅", "縺", "繧")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_html(path: Path, lines: list[str]) -> None:
    text = "\n".join(lines).encode("ascii", "xmlcharrefreplace").decode("ascii")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii")


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def batch_key_from_skill_path(path: Path) -> str | None:
    match = BATCH_RE.fullmatch(path.name)
    if not match:
        return None
    return f"original_{match.group(1)}_{match.group(2)}"


def batch_key_from_report_path(path: Path) -> str | None:
    match = REPORT_RE.fullmatch(path.name)
    if not match:
        return None
    return f"original_{match.group(1)}_{match.group(2)}"


def label_number(component: dict[str, Any]) -> str | None:
    label = component.get("condition_label")
    if isinstance(label, str):
        match = re.search(r"\d+", label)
        if match:
            return match.group(0)
    component_id = component.get("component_id") or ""
    match = re.search(r"_(\d+)$", component_id)
    return match.group(1) if match else None


def source_has_key_level(row: dict[str, Any], level: str) -> bool:
    return bool((row.get("values_by_denko_level") or {}).get(level))


def has_vu_only(component: dict[str, Any]) -> bool:
    availability = component.get("availability") or {}
    return bool(availability.get("vu_only"))


def component_text(component: dict[str, Any], include_raw_row: bool = True) -> str:
    parts: list[str] = []
    for key in ("condition_raw", "remarks_raw", "effect_kind"):
        value = component.get(key)
        if value:
            parts.append(str(value))
    for value in (component.get("values_by_denko_level") or {}).values():
        for key in ("value_raw", "source_text"):
            if value.get(key):
                parts.append(str(value[key]))
        raw_row = value.get("raw_row")
        if include_raw_row and isinstance(raw_row, dict):
            parts.extend(str(v) for v in raw_row.values() if v)
    return " / ".join(parts)


def component_primary_text(component: dict[str, Any]) -> str:
    parts: list[str] = []
    if component.get("condition_raw"):
        parts.append(str(component["condition_raw"]))
    for value in (component.get("values_by_denko_level") or {}).values():
        if value.get("value_raw"):
            parts.append(str(value["value_raw"]))
    return " / ".join(parts)


def force_hp_zero_text(text: str) -> bool:
    if "HPを0にできなかった" in text:
        return False
    if re.search(r"HPが0になっ|HP.*0になった", text):
        return False
    return bool(re.search(r"HPを0にする|HPを0にします", text))


def score_or_exp_is_condition_text(text: str, kind: str | None) -> bool:
    if kind in {"atk_buff", "atk_debuff"} and "ATK" in text and re.search(r"スコア.*時|スコア減少時", text):
        return True
    if kind in {"def_buff", "def_debuff"} and "DEF" in text and re.search(r"スコア.*時|経験値.*時", text):
        return True
    return False


def has_mixed_labeled_text(value: Any) -> bool:
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    labels = set(re.findall(r"[\(（](\d+)[\)）]", text))
    return len(labels) >= 2


def values_levels(component: dict[str, Any]) -> set[str]:
    return set((component.get("values_by_denko_level") or {}).keys())


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
    checks = {
        "ascii_only": ascii_only,
        "has_component_table": "技能分量表" in rendered,
        "has_vu_columns": all(col in rendered for col in ("Lv92内容", "Lv96内容", "Lv100内容")),
        "has_old_slot_matrix": "skill1_kind" in rendered or "skill1_condition" in rendered,
        "bad_hp_pattern": "HP?30%" in rendered,
        "double_question_count": rendered.count("??"),
        "mojibake_hits": {pattern: rendered.count(pattern) for pattern in MOJIBAKE_PATTERNS if rendered.count(pattern)},
    }
    if not ascii_only:
        add_issue(issues, batch, None, None, "medium", "report_encoding", "report_not_ascii_entity", "HTML report 不是 ASCII entity 输出，Windows 本地查看器可能误判编码。", fix_hint_zh="使用 write_html_entity_report 重新生成。")
    if not checks["has_component_table"]:
        add_issue(issues, batch, None, None, "high", "report_structure", "component_table_missing", "report 缺少一行一个 component 的技能分量表。", fix_hint_zh="重生成 report，或修 write_html_report。")
    if not checks["has_vu_columns"]:
        add_issue(issues, batch, None, None, "high", "report_structure", "vu_columns_missing", "report 缺少 Lv92/Lv96/Lv100 内容列，VU-only 技能容易被误判为空白。", fix_hint_zh="报告表格补 VU 三列。")
    if checks["has_old_slot_matrix"]:
        add_issue(issues, batch, None, None, "high", "report_structure", "old_5_slot_matrix", "report 仍包含旧 skill1_* 固定槽矩阵，容易产生空白 slot 误读。", fix_hint_zh="改为 component 长表。")
    if checks["bad_hp_pattern"] or checks["double_question_count"] or checks["mojibake_hits"]:
        add_issue(issues, batch, None, None, "critical", "encoding", "mojibake_or_question_damage", "report 中存在疑似乱码或 ? 替换损坏。", evidence=checks, fix_hint_zh="先用 UTF-8 JSONL/raw 复查，坏数据必须重跑或重写 patch。")
    return checks


def audit_skill_row(batch: str, row: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    denko_id = row.get("denko_id")
    name = row.get("name")
    components = row.get("skill_components") or []
    summary_zh = row.get("summary_zh") or ""
    if has_mixed_labeled_text(summary_zh):
        add_issue(issues, batch, denko_id, name, "medium", "summary", "summary_mixed_labeled_probability", "summary_zh 中仍混有多个编号概率/效果，可能没有复用 component 级拆分结果。", evidence=summary_zh[:300], fix_hint_zh="重建 summary_zh，概率按 component label 过滤。")
    labels = [component.get("condition_label") for component in components]
    first_label = next((label for label in labels if label), None)
    if first_label and first_label != "(1)":
        add_issue(issues, batch, denko_id, name, "high", "label", "first_label_not_1", "第一个带编号 component 不是 (1)，疑似主效果漏抓或排序错位。", evidence=labels, fix_hint_zh="复查条件表，补齐 (1) 或重排 component。")
    component_signatures: Counter[str] = Counter()
    for component in components:
        signature = json.dumps(
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
        component_signatures[signature] += 1
    for signature, count in component_signatures.items():
        if count > 1:
            add_issue(issues, batch, denko_id, name, "medium", "component", "duplicate_component_signature", "同一 denko 内存在完全相同的 component，疑似复制或拆分错位。", evidence={"count": count}, fix_hint_zh="人工或 LLM 片段复查。")
    for component in components:
        component_id = component.get("component_id")
        label = component.get("condition_label")
        label_num = label_number(component)
        component_id_num = None
        match = re.search(r"_(\d+)$", component_id or "")
        if match:
            component_id_num = match.group(1)
        if label_num and component_id_num and label_num != component_id_num:
            add_issue(issues, batch, denko_id, name, "high", "label", "label_component_id_mismatch", "condition_label 与 component_id 编号不一致。", component_id, fix_hint_zh="重命名或重建 component。", evidence={"label": label, "component_id": component_id})
        levels = values_levels(component)
        if label_num == "1" and levels and levels.issubset(VU_LEVELS) and not has_vu_only(component):
            add_issue(issues, batch, denko_id, name, "high", "vu", "primary_label_only_vu", "(1) 主效果只有 VU 等级，通常说明基础效果漏抓。", component_id, fix_hint_zh="复查 Lv30/Lv50 和条件表。")
        if not has_vu_only(component):
            for level in ("30", "50"):
                if source_has_key_level(row, level) and level not in levels:
                    add_issue(issues, batch, denko_id, name, "high", "level", f"non_vu_missing_lv{level}", f"非 VU component 缺 Lv{level}。", component_id, fix_hint_zh="复查技能等级表或确认该 component 是否应标 vu_only。")
        for level, value in (component.get("values_by_denko_level") or {}).items():
            probability = value.get("probability")
            if isinstance(probability, dict) and has_mixed_labeled_text(probability):
                add_issue(issues, batch, denko_id, name, "high", "probability", "mixed_labeled_probability", "probability 中仍混有多个 label。", component_id, evidence={"level": level, "probability": probability}, fix_hint_zh="按 component label 拆成独立 activation_probability。")
            value_raw = value.get("value_raw")
            if isinstance(value_raw, str) and label_num == "1" and "(2)" in value_raw:
                add_issue(issues, batch, denko_id, name, "high", "value", "base_value_contains_label_2", "(1) component 的 value_raw 中仍包含 (2)。", component_id, evidence={"level": level, "value_raw": value_raw}, fix_hint_zh="按 label 切分 value_raw。")
        review_reasons = set(component.get("review_reasons") or [])
        blockers = sorted(review_reasons & BLOCKING_REASONS)
        if blockers:
            add_issue(issues, batch, denko_id, name, "high", "blocking_reason", "component_has_blocking_reason", "component 仍带阻塞级 review reason。", component_id, evidence=blockers, fix_hint_zh="确定是 parser rule、manual fill、LLM snippet 还是 screenshot。")
        if component_id and component_id.startswith("component_"):
            add_issue(issues, batch, denko_id, name, "medium", "fallback", "fallback_component", "出现 fallback component，语义不稳定。", component_id, fix_hint_zh="复查原文并替换为语义 effect_kind。")
        text = component_text(component, include_raw_row=True)
        semantic_text = component_primary_text(component)
        kind = component.get("effect_kind")
        if force_hp_zero_text(semantic_text) and kind != "force_hp_zero":
            add_issue(issues, batch, denko_id, name, "high", "effect_kind", "hp_zero_not_force_hp_zero", "当前 component 日文含 HP を0にする，但 effect_kind 不是 force_hp_zero。", component_id, evidence=semantic_text[:300], fix_hint_zh="改为 force_hp_zero。")
        if (
            "スキル" in semantic_text
            and "無効" in semantic_text
            and "無効化されない" not in semantic_text
            and kind not in {"skill_disable", "supporter_disable"}
        ):
            add_issue(issues, batch, denko_id, name, "high", "effect_kind", "skill_disable_kind_mismatch", "当前 component 日文含スキル無効化，但 effect_kind 不匹配。", component_id, evidence=semantic_text[:300], fix_hint_zh="改为 skill_disable/supporter_disable。")
        if (
            ("経験値" in semantic_text or "スコア" in semantic_text)
            and kind in {"atk_buff", "def_buff", "atk_debuff", "def_debuff"}
            and not score_or_exp_is_condition_text(semantic_text, kind)
        ):
            add_issue(issues, batch, denko_id, name, "high", "effect_kind", "exp_score_text_in_atk_def_kind", "当前 component 日文含経験値/スコア，但 component 是 ATK/DEF 类，疑似邻接列错位。", component_id, evidence=semantic_text[:300], fix_hint_zh="复查效果类型，可能是 exp/score/no-reboot outcome。")
        if "経験値" in semantic_text and "分配" in semantic_text and kind == "exp_gain":
            add_issue(issues, batch, denko_id, name, "high", "effect_kind", "exp_distribution_not_exp_gain", "当前 component 是経験値分配，不应只建模为自身 exp_gain。", component_id, evidence=semantic_text[:300], fix_hint_zh="改为 exp_distribution 或补充分配对象。")
        condition_text = " / ".join(str(component.get(key) or "") for key in ("condition_raw", "remarks_raw"))
        if "相手" in condition_text and component.get("target_scope") in (["self"], ["team_all"]):
            filters = json.dumps(component.get("target_filters") or {}, ensure_ascii=False)
            trigger = json.dumps(component.get("trigger_conditions") or {}, ensure_ascii=False)
            if "opponent" not in filters and "opponent" not in trigger and "相手" not in filters and "相手" not in trigger:
                add_issue(issues, batch, denko_id, name, "medium", "target_condition", "opponent_condition_not_structured", "当前 component 条件中含相手，但未在 target_filters/trigger_conditions 中结构化 opponent 条件。", component_id, evidence=condition_text[:300], fix_hint_zh="确认相手是条件还是对象；若是条件，写 opponent_* filter。")
        trigger = component.get("trigger_conditions") or {}
        if ("アクセスされ" in semantic_text or "被アクセス" in semantic_text) and trigger.get("access_direction") == "active":
            add_issue(issues, batch, denko_id, name, "high", "trigger", "accessed_parsed_as_active", "日文是被访问/被攻击触发，但 trigger_conditions 写成 active access。", component_id, evidence=semantic_text[:300], fix_hint_zh="改为 access_direction=received。")
        if (
            "相手に" in semantic_text
            and kind in {"fixed_damage", "damage_reduction", "hp_recovery", "force_hp_zero"}
            and component.get("target_scope") == ["self"]
        ):
            add_issue(issues, batch, denko_id, name, "high", "target", "opponent_effect_targets_self", "日文效果对象是相手，但 target_scope 是 self。", component_id, evidence=semantic_text[:300], fix_hint_zh="target_scope 改为 opponent_denko 或补充 opponent target。")
        if ("自身を除" in semantic_text or "自分を除" in semantic_text) and component.get("target_scope") == ["self"]:
            add_issue(issues, batch, denko_id, name, "high", "target", "exclude_self_targets_self", "当前 component 写自身/自分を除く，但 target_scope 是 self。", component_id, evidence=semantic_text[:300], fix_hint_zh="target 改为目标车両/队伍范围，并写 exclude_self。")


def audit() -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    report_checks: dict[str, Any] = {}
    batches: dict[str, Any] = {}
    for report_path in sorted(base.REPORT_DIR.glob("original_*_batch_review_zh.html")):
        batch = batch_key_from_report_path(report_path)
        if batch:
            report_checks[batch] = audit_report(batch, report_path, issues)
    for skill_path in sorted(base.RECORD_DIR.glob("original_*_skill_facts.jsonl")):
        batch = batch_key_from_skill_path(skill_path)
        if not batch:
            continue
        rows = read_jsonl(skill_path)
        for row in rows:
            audit_skill_row(batch, row, issues)
        batches[batch] = {"skill_records": len(rows), "path": str(skill_path.relative_to(base.ROOT))}
    severity_counts = Counter(issue["severity"] for issue in issues)
    category_counts = Counter(issue["category"] for issue in issues)
    return {
        "schema_version": 1,
        "generated_at": datetime.now(base.JST).isoformat(),
        "scope": "original_001_163_existing_batches",
        "report_checks": report_checks,
        "batches": batches,
        "metrics": {
            "issue_count": len(issues),
            "severity_counts": dict(sorted(severity_counts.items())),
            "category_counts": dict(sorted(category_counts.items())),
        },
        "issues": issues,
    }


def write_markdown(path: Path, result: dict[str, Any]) -> None:
    lines = [
        "# Original 001-163 Report Checklist Audit",
        "",
        f"- generated_at: `{result['generated_at']}`",
        f"- scope: `{result['scope']}`",
        f"- issue_count: `{result['metrics']['issue_count']}`",
        f"- severity_counts: `{json.dumps(result['metrics']['severity_counts'], ensure_ascii=False, sort_keys=True)}`",
        f"- category_counts: `{json.dumps(result['metrics']['category_counts'], ensure_ascii=False, sort_keys=True)}`",
        "",
        "## Issues",
        "",
    ]
    if not result["issues"]:
        lines.append("本轮按 checklist 未检出问题。")
    else:
        lines.append("| severity | category | batch | denko | component | issue | detail | fix |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for issue in result["issues"]:
            denko = issue.get("denko_id") or ""
            name = issue.get("name") or ""
            denko_cell = f"{denko} {name}".strip()
            lines.append(
                "| "
                + " | ".join(
                    esc(issue.get(key, ""))
                    for key in ("severity", "category", "batch")
                )
                + f" | {esc(denko_cell)} | {esc(issue.get('component_id') or '')} | {esc(issue.get('issue'))} | {esc(issue.get('detail_zh'))} | {esc(issue.get('fix_hint_zh') or '')} |"
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default=str(base.ROOT / "data" / "agent_runs" / "original_001_163_report_checklist_audit.json"))
    parser.add_argument("--md-out", default=str(base.ROOT / "data" / "agent_runs" / "original_001_163_report_checklist_audit_zh.md"))
    args = parser.parse_args()
    result = audit()
    write_json(Path(args.json_out), result)
    write_markdown(Path(args.md_out), result)
    print(json.dumps({"issue_count": result["metrics"]["issue_count"], "json": args.json_out, "md": args.md_out}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
