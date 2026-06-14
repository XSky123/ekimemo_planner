from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import original_range_ingest as range_ingest
import parse as base
import review_cycle_controller as controller


BATCH_RE = re.compile(r"(?P<pool>original|extra)_(?P<start>\d{3})_(?P<end>\d{3})_skill_facts\.jsonl$")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def normalize_value_raw(component: dict[str, Any], value: dict[str, Any]) -> bool:
    raw = value.get("value_raw")
    label = component.get("condition_label")
    if not isinstance(raw, str) or not label:
        return False
    label_number = label.strip("()")
    original = raw
    if len(set(re.findall(r"[\(（](\d+)[\)）]", raw))) >= 2:
        extracted = base.extract_labeled_probability(raw, label_number)
        if extracted:
            value["value_raw"] = extracted
            return value["value_raw"] != original
    if label_number == "1" and "(2)" in raw:
        raw = raw.split("(2)")[0].strip()
    if raw.startswith(label):
        raw = raw[len(label) :].strip()
    value["value_raw"] = raw
    return value["value_raw"] != original


def inferred_probability_label(component: dict[str, Any]) -> str | None:
    label = component.get("condition_label")
    if label:
        return label
    text = " ".join(
        str(component.get(key) or "")
        for key in ("condition_raw", "effect_role", "component_id", "effect_kind")
    )
    if "(1)" in text and "(2)" not in text:
        return "(1)"
    if "(2)" in text and "(1)" not in text:
        return "(2)"
    if "primary_effect" in text or "base_effect" in text:
        return "(1)"
    return None


def inferred_probability_label_for_value(component: dict[str, Any], value: dict[str, Any]) -> str | None:
    label = inferred_probability_label(component)
    if label:
        return label
    raw_row = value.get("raw_row") or {}
    value_raw = str(value.get("value_raw") or "")
    for key, cell in raw_row.items():
        key_labels = re.findall(r"[\(\uff08](\d+)[\)\uff09]", str(key))
        if len(key_labels) != 1:
            continue
        if value_raw and value_raw in str(cell):
            return f"({key_labels[0]})"
    return None


def infer_unit(effect_kind: str, value_raw: str) -> str:
    if "～" in value_raw or "~" in value_raw or "〜" in value_raw:
        if "%" in value_raw or "％" in value_raw:
            return "percent_range"
        return "range"
    if "倍" in value_raw:
        return "multiplier"
    if "exp" in value_raw or "経験値" in value_raw:
        return "flat_exp"
    if "%" in value_raw or "％" in value_raw:
        return "percent"
    if "時間" in value_raw or "分" in value_raw:
        return "duration"
    if effect_kind in {"score_gain", "additional_score_gain"}:
        return "score"
    return "raw"


def value_from_row_fact(component: dict[str, Any], row_fact: dict[str, Any]) -> dict[str, Any] | None:
    value_raw = row_fact.get("effect")
    if not value_raw:
        return None
    effect_kind = str(component.get("effect_kind") or "")
    probability_label = inferred_probability_label(component)
    value = {
        "value_raw": value_raw,
        "value_numeric": base.parse_signed_number(value_raw),
        "unit": infer_unit(effect_kind, value_raw),
        "probability": base.probability_for_label(row_fact.get("probability") or {}, probability_label),
        "duration": row_fact.get("duration"),
        "cooldown": row_fact.get("cooldown"),
        "skill_level": row_fact.get("skill_level"),
        "source_text": row_fact.get("special_explanation"),
        "raw_row": row_fact.get("raw_row"),
    }
    value.update(base.range_value_fields(value_raw))
    return value


def labeled_effect_value(component: dict[str, Any], row_fact: dict[str, Any]) -> str | None:
    label = component.get("condition_label")
    if not label:
        return None
    label_number = str(label).strip("()")
    raw_row = row_fact.get("raw_row") or {}
    for key, cell in raw_row.items():
        key_labels = re.findall(r"[\(\uff08](\d+)[\)\uff09]", str(key))
        if len(key_labels) == 1 and key_labels[0] == label_number and cell:
            return str(cell).strip()
    effect = row_fact.get("effect")
    if isinstance(effect, str):
        segment = base.extract_labeled_condition_text(effect, f"({label_number})")
        if segment and segment != effect:
            return segment.strip()
    return None


def normalize_condition_only_value(component: dict[str, Any], value: dict[str, Any]) -> bool:
    effect_kind = component.get("effect_kind")
    raw = value.get("value_raw")
    row_fact = value.get("raw_row")
    if raw != effect_kind or not isinstance(row_fact, dict):
        return False
    source_row = {
        "effect": row_fact.get("効果") or " ".join(str(v) for k, v in row_fact.items() if "効果" in str(k) and v),
        "raw_row": row_fact,
    }
    labeled = labeled_effect_value(component, source_row)
    if not labeled:
        return False
    value["value_raw"] = labeled
    value["value_numeric"] = base.parse_signed_number(labeled)
    value["unit"] = infer_unit(str(effect_kind or ""), labeled)
    value.update(base.range_value_fields(labeled))
    return True


def normalize_fallback_component(component: dict[str, Any], row: dict[str, Any]) -> int:
    if not str(component.get("component_id") or "").startswith("component_"):
        return 0
    values = component.setdefault("values_by_denko_level", {})
    changed = 0
    for level, row_fact in (row.get("values_by_denko_level") or {}).items():
        if level in values:
            continue
        value = value_from_row_fact(component, row_fact)
        if value:
            values[level] = value
            changed += 1
    if changed:
        reasons = component.setdefault("review_reasons", [])
        component["review_reasons"] = [reason for reason in reasons if reason != "component_values_not_parsed"]
        component["confidence"] = "medium"
        component["needs_review"] = True
    return changed


def normalize_fallback_component_id(component: dict[str, Any], used_ids: set[str]) -> bool:
    component_id = str(component.get("component_id") or "")
    if not component_id.startswith("component_"):
        used_ids.add(component_id)
        return False
    effect_kind = str(component.get("effect_kind") or "")
    if not effect_kind or effect_kind in used_ids:
        used_ids.add(component_id)
        return False
    component["component_id"] = effect_kind
    used_ids.add(effect_kind)
    return True


def refresh_component_review_reasons(row: dict[str, Any]) -> int:
    components = row.get("skill_components") or []
    condition_text = " ".join(str(component.get("condition_raw") or "") for component in components)
    expected_labels = {label.strip("()") for label, _segment in base.labeled_condition_segments(condition_text)}
    emitted_labels = {
        str(component.get("condition_label")).strip("()")
        for component in components
        if component.get("condition_label")
    }
    duplicate_ids = base.component_duplicate_signatures(components)
    changed = 0
    for component in components:
        before = list(component.get("review_reasons") or [])
        after = list(before)
        component_id = component.get("component_id") or ""
        if expected_labels and expected_labels.issubset(emitted_labels):
            after = [reason for reason in after if reason != "labeled_component_count_mismatch"]
        if component_id not in duplicate_ids:
            after = [reason for reason in after if reason != "duplicate_labeled_component_values_need_review"]
        if not base.has_condition_effect_mismatch(component):
            after = [reason for reason in after if reason != "condition_effect_mismatch_needs_review"]
        if not (
            base.label_declared_vu_only(component, condition_text)
            and not base.component_has_only_vu_values(component)
        ):
            after = [reason for reason in after if reason != "vu_label_level_mismatch_needs_review"]
        if after != before:
            component["review_reasons"] = after
            changed += 1
    return changed


def normalize_skill_rows(rows: list[dict[str, Any]]) -> int:
    changed = 0
    for row in rows:
        used_ids: set[str] = set()
        for component in row.get("skill_components") or []:
            changed += normalize_fallback_component(component, row)
            if normalize_fallback_component_id(component, used_ids):
                changed += 1
            for value in (component.get("values_by_denko_level") or {}).values():
                before = json.dumps(value, ensure_ascii=False, sort_keys=True)
                probability = value.get("probability")
                label = inferred_probability_label_for_value(component, value)
                if isinstance(probability, dict) and label:
                    value["probability"] = base.probability_for_label(probability, label)
                normalize_condition_only_value(component, value)
                normalize_value_raw(component, value)
                after = json.dumps(value, ensure_ascii=False, sort_keys=True)
                if before != after:
                    changed += 1
        row["summary_zh"] = base.build_summary_zh(
            row.get("skill_components"),
            row.get("normalized_skill"),
            (row.get("values_by_denko_level") or {}).get("50"),
            row.get("values_by_denko_level"),
        )
        changed += refresh_component_review_reasons(row)
    return changed


def rebuild_outputs(pool: str, start: int, end: int, batch_size: int) -> dict[str, str]:
    stem = range_ingest.output_stem(start, end, pool)
    denko_rows = read_jsonl(base.RECORD_DIR / f"{stem}_denko_facts.jsonl")
    skill_rows = read_jsonl(base.RECORD_DIR / f"{stem}_skill_facts.jsonl")
    reviews = read_jsonl(base.REVIEW_DIR / f"{stem}_review_queue.jsonl")
    report = range_ingest.write_html_report(start, end, denko_rows, skill_rows, reviews, batch_size, pool)
    state = controller.build_state(start, end, batch_size, run_result=None, pool=pool)
    state["paths"]["report"] = str(report.relative_to(base.ROOT))
    state_path = controller.AGENT_RUN_DIR / f"{stem}_cycle_state.json"
    controller.write_json(state_path, state)
    prompt = controller.write_batch_review_prompt(stem, state)
    return {
        "report": str(report.relative_to(base.ROOT)),
        "state": str(state_path.relative_to(base.ROOT)),
        "agent_prompt": str(prompt.relative_to(base.ROOT)),
    }


def normalize_file(path: Path, batch_size: int, rebuild: bool) -> dict[str, Any]:
    match = BATCH_RE.fullmatch(path.name)
    if not match:
        raise ValueError(f"unsupported skill facts filename: {path.name}")
    pool = match.group("pool")
    start = int(match.group("start"))
    end = int(match.group("end"))
    rows = read_jsonl(path)
    changed = normalize_skill_rows(rows)
    write_jsonl(path, rows)
    outputs = rebuild_outputs(pool, start, end, batch_size) if rebuild else {}
    return {
        "path": str(path.relative_to(base.ROOT)),
        "pool": pool,
        "start": start,
        "end": end,
        "records": len(rows),
        "changed_values": changed,
        **outputs,
    }


def selected_paths(pool: str | None, pattern: str | None) -> list[Path]:
    if pattern:
        return sorted(base.RECORD_DIR.glob(pattern))
    prefix = f"{pool}_" if pool else ""
    return sorted(base.RECORD_DIR.glob(f"{prefix}*_skill_facts.jsonl"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", choices=sorted(base.LIST_PAGES))
    parser.add_argument("--pattern", help="Optional glob under data/records, e.g. extra_*_skill_facts.jsonl")
    parser.add_argument("--batch-size", type=int, default=30)
    parser.add_argument("--no-rebuild", action="store_true")
    args = parser.parse_args()
    results = [
        normalize_file(path, args.batch_size, rebuild=not args.no_rebuild)
        for path in selected_paths(args.pool, args.pattern)
    ]
    print(json.dumps({"normalized_files": len(results), "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
