from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Any

# jsonschema emits this while importing its legacy resolver. The resolver is
# intentionally kept for local file refs until the project upgrades it.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from jsonschema import Draft202012Validator, RefResolver


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "schemas" / "role_profile.schema.json"
PROFILES_PATH = ROOT / "data" / "role_profiles" / "role_profiles.jsonl"
OUT = ROOT / "data" / "audits" / "step3_role_profile_schema_audit.json"


def main() -> int:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    resolver = RefResolver(base_uri=SCHEMA_PATH.as_uri(), referrer=schema)
    validator = Draft202012Validator(schema, resolver=resolver)
    errors: list[dict[str, Any]] = []
    count = 0
    for line_number, line in enumerate(PROFILES_PATH.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        count += 1
        row = json.loads(line)
        for error in validator.iter_errors(row):
            errors.append({
                "line": line_number,
                "profile_id": row.get("profile_id"),
                "path": "/".join(str(item) for item in error.path),
                "message": error.message,
            })
            if len(errors) >= 50:
                break
        if len(errors) >= 50:
            break
    result = {
        "artifact": "step3_role_profile_schema_audit",
        "schema": str(SCHEMA_PATH.relative_to(ROOT)),
        "profiles": count,
        "issue_count": len(errors),
        "issues": errors,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"profiles": count, "issue_count": len(errors)}, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
