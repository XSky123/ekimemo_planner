from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RATINGS = ROOT / "data/role_profiles/denko_ratings.jsonl"
OUT = ROOT / "data/audits/step3_scored_component_condition_audit.json"
CATEGORIES = ("attack_front", "defense_front", "attack_support", "defense_support", "score_gain", "exp_gain")
HIGH_RISK_TERMS = ("場合", "以上", "以下", "応じ", "属性", "以内", "距離", "曜日", "天気", "上限")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    ratings = read_jsonl(RATINGS)
    findings: list[dict[str, Any]] = []
    checked: set[tuple[str, str, str]] = set()
    for level in ("50", "80"):
        for category in CATEGORIES:
            eligible = [row for row in ratings if row["levels"][level]["role_scores"][category] > 0]
            ordered = sorted(eligible, key=lambda row: (-row["levels"][level]["role_scores"][category], row["rating_id"]))
            for band, rows in (("top15", ordered[:15]), ("bottom15", ordered[-15:])):
                for row in rows:
                    for component in row["levels"][level]["use_case_components"][category]:
                        key = (level, category, component["profile_id"])
                        if key in checked:
                            continue
                        checked.add(key)
                        raw = str(component["factors"].get("condition_raw") or "")
                        details = component["factors"].get("condition_details") or []
                        if any(term in raw for term in HIGH_RISK_TERMS) and not details:
                            findings.append({
                                "level": level, "category": category, "band": band,
                                "denko_id": row["rating_id"], "profile_id": component["profile_id"],
                                "condition_raw": raw, "reason_zh": "计分组件含高风险条件词，但未生成结构化条件因子。",
                            })
    result = {
        "artifact": "step3_scored_component_condition_audit",
        "checked_components": len(checked), "finding_count": len(findings),
        "findings": findings, "issue_count": len(findings),
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"checked_components": len(checked), "finding_count": len(findings)}, ensure_ascii=False))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
