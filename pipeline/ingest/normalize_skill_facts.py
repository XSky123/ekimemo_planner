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


def normalize_skill_rows(rows: list[dict[str, Any]]) -> int:
    changed = 0
    for row in rows:
        for component in row.get("skill_components") or []:
            label = component.get("condition_label")
            for value in (component.get("values_by_denko_level") or {}).values():
                before = json.dumps(value, ensure_ascii=False, sort_keys=True)
                probability = value.get("probability")
                if isinstance(probability, dict) and label:
                    value["probability"] = base.probability_for_label(probability, label)
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
