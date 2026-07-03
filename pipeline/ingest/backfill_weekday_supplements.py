from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import parse as base
from pipeline.analysis import write_exp_pt_support_rankings as exp_report
from pipeline.ingest.backfill_exp_pt_supplements import is_auto_backfill_locked


BACKFILL_VERSION = "weekday_skill_table_supplements.v1"
REASON = "stable_weekday_table_supplement"
SOURCE_GLOB = "*_skill_facts.jsonl"

WEEKDAY_EFFECTS = {
    "weekday_atk_sunday": ("日曜日", "ATK増加", "atk_buff", "percent", "ATK "),
    "weekday_atk_tuesday": ("火曜日", "ATK増加 DEF増加", "atk_buff", "percent", "ATK "),
    "weekday_def_monday": ("月曜日", "DEF増加", "def_buff", "percent", "DEF "),
    "weekday_def_tuesday": ("火曜日", "ATK増加 DEF増加", "def_buff", "percent", "DEF "),
    "weekday_fixed_damage_wednesday": ("水曜日", "固定ダメージ", "fixed_damage", "flat_damage", "固定ダメージ "),
    "weekday_damage_reduction_thursday": ("木曜日", "ダメージ軽減", "damage_reduction", "flat_damage", "ダメージ軽減 "),
    "weekday_score_gain_friday": ("金曜日", "スコア獲得", "score_gain", "score", "スコア獲得 "),
    "weekday_exp_gain_saturday": ("土曜日", "経験値獲得", "exp_gain", "flat_exp", "経験値獲得 "),
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def numbers(text: str) -> list[float]:
    out: list[float] = []
    cleaned = text.replace("％", "%").replace("（", "").replace("）", "")
    for raw in re.findall(r"[+-]?\d+(?:\.\d+)?", cleaned):
        out.append(float(raw))
    return out


def value_for_component(component_id: str, cell: str, unit: str) -> tuple[float | None, float | None, float | None, str]:
    vals = numbers(cell)
    if not vals:
        return None, None, None, cell
    if component_id.endswith("_tuesday") and len(vals) >= 2:
        value = vals[0] if "atk" in component_id else vals[1]
    else:
        value = vals[0]
    if unit == "percent":
        normalized = f"+{value:g}%"
    else:
        normalized = f"{value:g}"
    return value, value, value, normalized


def supplement_value(denko_id: str, component: dict[str, Any], value: dict[str, Any], level: str) -> dict[str, Any] | None:
    component_id = str(component.get("component_id") or "")
    spec = WEEKDAY_EFFECTS.get(component_id)
    if not spec:
        return None
    if is_auto_backfill_locked(component, value):
        return None
    day_raw, effect_raw, expected_kind, unit, prefix = spec
    if component.get("effect_kind") != expected_kind:
        return None
    table_level = level if level in exp_report.raw_detail_weekday_values(denko_id) else "80"
    cell = exp_report.raw_detail_weekday_values(denko_id).get(table_level, {}).get(day_raw, {}).get(effect_raw)
    if not cell:
        return None
    value_numeric, value_min, value_max, normalized_cell = value_for_component(component_id, cell, unit)
    suffix = f" ※曜日表Lv{table_level}基準" if table_level != level else ""
    return {
        **value,
        "unit": unit,
        "value_numeric": value_numeric,
        "value_min": value_min,
        "value_max": value_max,
        "value_raw": prefix + normalized_cell + suffix,
        "db_backfilled_from": "detail_raw_weekday_table",
        "db_backfill_reason": REASON,
        "db_backfill_version": BACKFILL_VERSION,
        "report_supplemented_from": "detail_raw_weekday_table",
        "report_weekday_table_level": table_level,
    }


def value_signature(value: dict[str, Any]) -> dict[str, Any]:
    keys = {"unit", "value_numeric", "value_min", "value_max", "value_raw", "report_weekday_table_level"}
    return {key: value.get(key) for key in sorted(keys) if key in value}


def backfill_row(row: dict[str, Any]) -> dict[str, Any]:
    denko_id = row.get("denko_id")
    if not denko_id:
        return {"changed": 0, "sources": Counter()}
    changed = 0
    sources: Counter[str] = Counter()
    for component in row.get("skill_components") or []:
        values = component.get("values_by_denko_level") or {}
        for level, value in list(values.items()):
            if not isinstance(value, dict):
                continue
            supplement = supplement_value(str(denko_id), component, value, str(level))
            if not supplement:
                continue
            if value_signature(supplement) == value_signature(value):
                continue
            values[str(level)] = supplement
            changed += 1
            sources["detail_raw_weekday_table"] += 1
    if changed:
        row["summary_zh"] = base.build_summary_zh(
            row.get("skill_components") or [],
            row.get("normalized_skill") or {},
            row.get("lv50") or {},
            row.get("values_by_denko_level") or {},
        )
        meta = row.setdefault("record_meta", {})
        postprocess = meta.setdefault("postprocess", {})
        postprocess["weekday_db_backfill"] = {
            "version": BACKFILL_VERSION,
            "reason": REASON,
            "changed_values": changed,
            "sources": dict(sorted(sources.items())),
        }
    return {"changed": changed, "sources": sources}


def backfill_file(path: Path, dry_run: bool) -> dict[str, Any]:
    rows = read_jsonl(path)
    changed_rows = 0
    changed_values = 0
    sources: Counter[str] = Counter()
    changed_ids: list[str] = []
    for row in rows:
        result = backfill_row(row)
        if result["changed"]:
            changed_rows += 1
            changed_values += int(result["changed"])
            sources.update(result["sources"])
            changed_ids.append(row.get("denko_id") or "")
    if changed_rows and not dry_run:
        write_jsonl(path, rows)
    return {
        "path": str(path.relative_to(ROOT)),
        "changed_rows": changed_rows,
        "changed_values": changed_values,
        "sources": dict(sorted(sources.items())),
        "denko_ids": changed_ids,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--records-dir", type=Path, default=base.RECORD_DIR)
    args = parser.parse_args()

    results = [backfill_file(path, args.dry_run) for path in sorted(args.records_dir.glob(SOURCE_GLOB))]
    totals = {
        "dry_run": args.dry_run,
        "backfill_version": BACKFILL_VERSION,
        "changed_rows": sum(item["changed_rows"] for item in results),
        "changed_values": sum(item["changed_values"] for item in results),
        "files": [item for item in results if item["changed_rows"]],
    }
    print(json.dumps(totals, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
