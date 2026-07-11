from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROFILES = ROOT / "data" / "role_profiles" / "role_profiles.jsonl"
CASES = ROOT / "steps" / "step3_role_profiles" / "role_profile_regression_cases.json"


def nested(row: dict[str, Any], path: str) -> Any:
    current: Any = row
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def derived_collections(row: dict[str, Any]) -> dict[str, list[Any]]:
    return {
        "scene_ids": [item["id"] for item in row.get("scene_tags") or []],
        "recipient": row.get("component", {}).get("recipient") or [],
        "opportunity_costs": row.get("constraints", {}).get("opportunity_costs") or [],
        "self_debuff_kinds": [item.get("effect_kind") for item in row.get("constraints", {}).get("self_debuff") or []],
        "hard_constraint_keys": [item.get("key") for item in row.get("constraints", {}).get("hard") or []],
        "target_filter_keys": list((row.get("component", {}).get("target_filters") or {}).keys()),
    }


def main() -> int:
    profiles = {row["profile_id"]: row for row in (json.loads(line) for line in PROFILES.read_text(encoding="utf-8").splitlines() if line.strip())}
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    failures: list[str] = []
    for case in cases:
        row = profiles.get(case["profile_id"])
        if row is None:
            failures.append(f"{case['id']}: profile missing")
            continue
        derived = derived_collections(row)
        for path, expected in (case.get("equals") or {}).items():
            actual = nested(row, path)
            if actual != expected:
                failures.append(f"{case['id']}: {path} expected {expected!r}, got {actual!r}")
        for name, expected in (case.get("contains") or {}).items():
            actual = derived.get(name) if name in derived else nested(row, name)
            expected_values = expected if isinstance(expected, list) else [expected]
            if not isinstance(actual, list) or any(value not in actual for value in expected_values):
                failures.append(f"{case['id']}: {name} should contain {expected!r}, got {actual!r}")
        for path in case.get("absent") or []:
            if nested(row, path) is not None:
                failures.append(f"{case['id']}: {path} should be absent")
    result = {"cases": len(cases), "failures": len(failures), "details": failures}
    print(json.dumps(result, ensure_ascii=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
