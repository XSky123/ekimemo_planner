from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RATINGS = ROOT / "data/role_profiles/denko_ratings.jsonl"
SCENES = (
    "daily_attack", "burst_attack", "home_defense", "expedition_score",
    "expedition_exp", "growth", "mechanism",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def compact_component(component: dict[str, Any]) -> dict[str, Any]:
    factors = component["factors"]
    return {
        "profile_id": component["profile_id"],
        "effect": component["effect_kind"],
        "utility": component["utility"],
        "value": factors.get("magnitude_value"),
        "probability": factors.get("probability"),
        "availability": factors.get("availability"),
        "condition": factors.get("condition"),
        "conditions": [item["key"] for item in factors.get("condition_details") or []],
        "scope": factors.get("scope_basis"),
        "costs": factors.get("cost_details") or [],
    }


def build(round_number: int, level: str) -> list[dict[str, Any]]:
    ratings = read_jsonl(RATINGS)
    result = []
    for scene in SCENES:
        eligible = [
            row for row in ratings
            if row["levels"][level]["scenes"][scene]["top_components"]
        ]
        ordered = sorted(
            eligible,
            key=lambda row: (-row["levels"][level]["scenes"][scene]["score"], row["rating_id"]),
        )
        selections = [("top", index + 1, row) for index, row in enumerate(ordered[:15])]
        selections += [("bottom", len(ordered) - 14 + index, row) for index, row in enumerate(ordered[-15:])]
        for band, rank, row in selections:
            payload = row["levels"][level]["scenes"][scene]
            result.append({
                "review_id": f"r{round_number}:{level}:{scene}:{band}:{row['rating_id']}",
                "round": round_number, "level": level, "scene": scene,
                "band": band, "rank": rank,
                "denko_id": row["rating_id"], "name": row["denko"].get("name"),
                "attribute": row["denko"].get("attribute"), "type": row["denko"].get("type"),
                "scene_score": payload["score"], "scene_utility": payload["utility"],
                "beginner_model_score": row["levels"]["50"].get("model_score"),
                "beginner_published_score": row["levels"]["50"].get("published_score"),
                "veteran_overall_score": row["levels"]["80"]["overall_score"],
                "wiki_marker": row["calibration"].get("beginner_prior_marker"),
                "wiki_reason_ja": row["calibration"].get("wiki_reason_ja"),
                "components": [compact_component(item) for item in payload["top_components"]],
                "llm_review": None,
            })
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round", type=int, required=True, choices=(1, 2))
    parser.add_argument("--level", default="80", choices=("50", "80"))
    args = parser.parse_args()
    rows = build(args.round, args.level)
    out = ROOT / "data/review_queue" / f"step3_rating_llm_round{args.round}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8", newline="\n")
    print(json.dumps({"round": args.round, "level": args.level, "rows": len(rows), "output": str(out.relative_to(ROOT))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
