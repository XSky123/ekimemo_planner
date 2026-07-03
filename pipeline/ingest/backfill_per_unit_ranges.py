from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


BACKFILL_VERSION = "per_unit_range.v1"
REASON = "stable_per_unit_formula_range"
SOURCE_GLOB = "*_skill_facts.jsonl"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def as_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def find_multiplier(raw: str) -> float | None:
    patterns = [
        r"[+＋]?\s*n\s*駅?\s*[×xX]\s*(\d+(?:\.\d+)?)\s*%",
        r"[+＋]?\s*(\d+(?:\.\d+)?)\s*[×xX]\s*n\s*駅?\s*%",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw, flags=re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def max_count_from_component(component: dict[str, Any]) -> float | None:
    for container_key in ("target_filters", "scaling_conditions"):
        container = component.get(container_key) or {}
        for key in (
            "max_station_count",
            "max_count",
            "max_linked_station_count",
            "max_units",
            "max_n",
        ):
            number = as_number(container.get(key))
            if number is not None:
                return number

    context = " ".join(
        str(item or "")
        for item in (
            component.get("condition_raw"),
            component.get("remarks_raw"),
            json.dumps(component.get("target_filters") or {}, ensure_ascii=False),
            json.dumps(component.get("scaling_conditions") or {}, ensure_ascii=False),
        )
    )
    match = re.search(r"(?:上限|最大)\s*(\d+(?:\.\d+)?)\s*(?:駅|体|人|両|個)?", context)
    if match:
        return float(match.group(1))
    return None


def backfill_value(component: dict[str, Any], value: dict[str, Any]) -> bool:
    if value.get("value_min") is not None or value.get("value_max") is not None:
        return False

    raw = str(value.get("value_raw") or "")
    multiplier = find_multiplier(raw)
    if multiplier is None and value.get("unit") == "percent_per_station":
        multiplier = as_number(value.get("value_numeric"))
    max_count = max_count_from_component(component)
    if multiplier is None or max_count is None:
        return False

    value["unit"] = value.get("unit") or "percent_range"
    value["value_min"] = 0.0
    value["value_max"] = multiplier * max_count
    value["value_numeric"] = multiplier
    value["db_backfilled_from"] = "per_unit_formula"
    value["db_backfill_reason"] = REASON
    value["db_backfill_version"] = BACKFILL_VERSION
    return True


def backfill_row(row: dict[str, Any]) -> tuple[dict[str, Any], int]:
    changed_values = 0
    for component in row.get("skill_components") or []:
        values = component.get("values_by_denko_level") or {}
        for value in values.values():
            if backfill_value(component, value):
                changed_values += 1

    if changed_values:
        postprocess = row.setdefault("record_meta", {}).setdefault("postprocess", {})
        postprocess["per_unit_range_backfill"] = {
            "backfill_version": BACKFILL_VERSION,
            "changed_values": changed_values,
            "reason": REASON,
        }
    return row, changed_values


def backfill_file(path: Path, dry_run: bool) -> dict[str, Any]:
    rows = read_jsonl(path)
    new_rows = []
    changed_rows = 0
    changed_values = 0
    for row in rows:
        new_row, row_changed_values = backfill_row(row)
        new_rows.append(new_row)
        if row_changed_values:
            changed_rows += 1
            changed_values += row_changed_values
    if changed_rows and not dry_run:
        write_jsonl(path, new_rows)
    return {"path": str(path), "changed_rows": changed_rows, "changed_values": changed_values}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records-dir", type=Path, default=ROOT / "data" / "records")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    results = [backfill_file(path, args.dry_run) for path in sorted(args.records_dir.glob(SOURCE_GLOB))]
    print(json.dumps({"backfill_version": BACKFILL_VERSION, "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
