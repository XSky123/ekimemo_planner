from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import parse as base
from pipeline.analysis import write_exp_pt_support_rankings as exp_report


BACKFILL_VERSION = "exp_pt_report_supplements.v1"
REASON = "stable_exp_pt_report_supplement"
SOURCE_GLOB = "*_skill_facts.jsonl"
LOCK_REASONS = {
    "manual_semantic_fill",
    "manual_condition_split_fix",
    "manual_value_override",
    "manual_verified_stable",
}
LOCK_KEYS = {
    "db_backfill_lock",
    "manual_override",
    "manual_verified",
    "stable_manual_review",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def clean_supplement(value: dict[str, Any]) -> dict[str, Any] | None:
    if value.get("unit") == "report_ignore":
        return None
    out = {key: item for key, item in value.items() if key != "_report_level"}
    source = out.get("report_supplemented_from")
    if source:
        out["db_backfilled_from"] = source
    out["db_backfill_reason"] = REASON
    out["db_backfill_version"] = BACKFILL_VERSION
    return out


def value_signature(value: dict[str, Any]) -> dict[str, Any]:
    keys = {
        "unit",
        "value_numeric",
        "value_min",
        "value_max",
        "value_raw",
        "probability",
        "report_supplemented_from",
        "report_weekday_table_level",
    }
    return {key: value.get(key) for key in sorted(keys) if key in value}


def has_lock_marker(item: dict[str, Any]) -> bool:
    if any(item.get(key) for key in LOCK_KEYS):
        return True
    if item.get("manual_patch_ids"):
        return True
    reasons = set(item.get("review_reasons") or [])
    return bool(reasons & LOCK_REASONS)


def is_auto_backfill_locked(component: dict[str, Any], value: dict[str, Any]) -> bool:
    if has_lock_marker(value):
        return True
    if component.get("db_backfill_lock"):
        return True
    if component.get("manual_patch_ids"):
        return True
    reasons = set(component.get("review_reasons") or [])
    return bool(reasons & LOCK_REASONS)


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
            if is_auto_backfill_locked(component, value):
                continue
            supplement = exp_report.supplemental_value_from_raw_page(denko_id, component, value, str(level))
            if not supplement:
                continue
            cleaned = clean_supplement(supplement)
            if not cleaned:
                continue
            if value_signature(cleaned) == value_signature(value):
                continue
            values[str(level)] = cleaned
            changed += 1
            source = cleaned.get("db_backfilled_from") or cleaned.get("report_supplemented_from") or "unknown"
            sources[str(source)] += 1

    if changed:
        row["summary_zh"] = base.build_summary_zh(
            row.get("skill_components") or [],
            row.get("normalized_skill") or {},
            row.get("lv50") or {},
            row.get("values_by_denko_level") or {},
        )
        meta = row.setdefault("record_meta", {})
        postprocess = meta.setdefault("postprocess", {})
        postprocess["exp_pt_db_backfill"] = {
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

    files = sorted(args.records_dir.glob(SOURCE_GLOB))
    results = [backfill_file(path, args.dry_run) for path in files]
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
