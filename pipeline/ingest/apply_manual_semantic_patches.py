from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import original_range_ingest as range_ingest
import parse as base
import review_cycle_controller


MANUAL_FILL_DIR = base.ROOT / "data" / "manual_fills"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )


def component_id_from_field_path(field_path: str) -> str | None:
    match = re.search(r"component_id=([^\]]+)", field_path)
    return match.group(1) if match else None


def find_component(components: list[dict[str, Any]], component_id: str) -> tuple[int, dict[str, Any]] | tuple[None, None]:
    for index, component in enumerate(components):
        if component.get("component_id") == component_id:
            return index, component
    return None, None


def dedupe_components(components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for component in components:
        component_id = component.get("component_id")
        if not component_id:
            continue
        if component_id not in by_id:
            order.append(component_id)
        by_id[component_id] = component
    return [by_id[component_id] for component_id in order]


def deep_merge(target: dict[str, Any], patch_value: dict[str, Any]) -> None:
    for key, value in patch_value.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_merge(target[key], value)
        else:
            target[key] = deepcopy(value)


def normalize_component(component: dict[str, Any], patch_id: str) -> dict[str, Any]:
    out = deepcopy(component)
    out.setdefault("target_scope", [])
    out.setdefault("target_filters", {})
    out.setdefault("trigger_conditions", {})
    out.setdefault("scaling_conditions", {})
    out.setdefault("values_by_denko_level", {})
    out.setdefault("confidence", "medium")
    out.setdefault("needs_review", False)
    mark_component_with_patch(out, patch_id)
    return out


def mark_component_with_patch(component: dict[str, Any], patch_id: str) -> None:
    reasons = component.setdefault("review_reasons", [])
    if "manual_semantic_fill" not in reasons:
        reasons.append("manual_semantic_fill")
    patch_ids = component.setdefault("manual_patch_ids", [])
    if patch_id not in patch_ids:
        patch_ids.append(patch_id)


def apply_patch_to_skill_row(row: dict[str, Any], patch: dict[str, Any]) -> bool:
    operation = patch["patch"]["operation"]
    field_path = patch["patch"]["field_path"]
    value = patch["patch"]["value"]
    components = row.setdefault("skill_components", [])
    changed = False

    if operation == "add_component":
        component = normalize_component(value, patch["patch_id"])
        existing_index, _existing = find_component(components, component["component_id"])
        if existing_index is None:
            components.append(component)
        else:
            components[existing_index] = component
        changed = True
    elif operation == "replace_component":
        component_id = component_id_from_field_path(field_path)
        if not component_id:
            raise ValueError(f"replace_component requires component_id field path: {field_path}")
        existing_index, _existing = find_component(components, component_id)
        if value.get("superseded_by"):
            if existing_index is not None:
                del components[existing_index]
            changed = True
        else:
            component = normalize_component(value, patch["patch_id"])
            if existing_index is None:
                existing_index, _existing = find_component(components, component["component_id"])
            if existing_index is None:
                components.append(component)
            else:
                components[existing_index] = component
            changed = True
    elif operation in {"merge", "set"}:
        component_id = component_id_from_field_path(field_path)
        if not component_id:
            raise ValueError(f"{operation} requires component_id field path: {field_path}")
        _existing_index, existing = find_component(components, component_id)
        if existing is None:
            raise ValueError(f"component not found for patch {patch['patch_id']}: {component_id}")
        if operation == "merge":
            deep_merge(existing, value)
        else:
            existing.clear()
            existing.update(deepcopy(value))
        mark_component_with_patch(existing, patch["patch_id"])
        changed = True
    else:
        raise ValueError(f"unsupported patch operation: {operation}")

    if changed:
        record_meta = row.setdefault("record_meta", {})
        patch_ids = record_meta.setdefault("manual_patch_ids", [])
        if patch["patch_id"] not in patch_ids:
            patch_ids.append(patch["patch_id"])
        record_meta["manual_patch_applied"] = True
        record_meta["manual_patch_source"] = "data/manual_fills"
        row["skill_components"] = sorted(dedupe_components(components), key=base.component_sort_key)
    return changed


def accept_patches(patches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    accepted = []
    for patch in patches:
        if patch.get("status") in {"proposed", "accepted"}:
            patch = deepcopy(patch)
            patch["status"] = "accepted"
            accepted.append(patch)
    return accepted


def apply_patches(batch: str) -> dict[str, Any]:
    patch_path = MANUAL_FILL_DIR / f"{batch}_semantic_patches.jsonl"
    patches = accept_patches(read_jsonl(patch_path))
    if not patches:
        raise SystemExit(f"No proposed/accepted patches found: {patch_path}")

    skill_path = base.RECORD_DIR / f"{batch}_skill_facts.jsonl"
    denko_path = base.RECORD_DIR / f"{batch}_denko_facts.jsonl"
    review_path = base.REVIEW_DIR / f"{batch}_review_queue.jsonl"
    skill_rows = read_jsonl(skill_path)
    denko_rows = read_jsonl(denko_path)
    reviews = read_jsonl(review_path)
    by_id = {row["denko_id"]: row for row in skill_rows}

    applied_patch_ids = []
    for patch in patches:
        row = by_id.get(patch["denko_id"])
        if row is None:
            raise ValueError(f"denko not found for patch {patch['patch_id']}: {patch['denko_id']}")
        if apply_patch_to_skill_row(row, patch):
            applied_patch_ids.append(patch["patch_id"])

    write_jsonl(skill_path, skill_rows)
    write_jsonl(patch_path, patches)

    start, end = batch_range(batch)
    report_path = range_ingest.write_html_report(start, end, denko_rows, skill_rows, reviews, batch_size=30)
    state = review_cycle_controller.build_state(start, end, 30, run_result=None)
    state["manual_patch_application"] = {
        "applied_at": datetime.now(base.JST).isoformat(),
        "patch_file": str(patch_path.relative_to(base.ROOT)),
        "applied_patch_ids": applied_patch_ids,
    }
    state["paths"]["report"] = str(report_path.relative_to(base.ROOT))
    state_path = review_cycle_controller.AGENT_RUN_DIR / f"{batch}_cycle_state.json"
    review_cycle_controller.write_json(state_path, state)
    prompt_path = review_cycle_controller.write_batch_review_prompt(batch, state)
    return {
        "patch_file": str(patch_path.relative_to(base.ROOT)),
        "applied_patch_count": len(applied_patch_ids),
        "applied_patch_ids": applied_patch_ids,
        "skill_facts": str(skill_path.relative_to(base.ROOT)),
        "report": str(report_path.relative_to(base.ROOT)),
        "state": str(state_path.relative_to(base.ROOT)),
        "agent_prompt": str(prompt_path.relative_to(base.ROOT)),
        "blocking_item_count": state["metrics"]["blocking_item_count"],
    }


def batch_range(batch: str) -> tuple[int, int]:
    match = re.fullmatch(r"original_(\d{3})_(\d{3})", batch)
    if not match:
        raise ValueError(f"unsupported batch name: {batch}")
    return int(match.group(1)), int(match.group(2))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", required=True)
    args = parser.parse_args()
    print(json.dumps(apply_patches(args.batch), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
