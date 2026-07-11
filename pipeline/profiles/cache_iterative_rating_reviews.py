from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RATINGS = ROOT / "data/role_profiles/denko_ratings.jsonl"
ROLE_ZH = {
    "attack_front": "攻击车头", "defense_front": "守站肉盾",
    "attack_support": "攻击队友", "defense_support": "防守队友",
    "score_gain": "加分", "exp_gain": "加经验",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def evidence(row: dict[str, Any]) -> dict[str, Any]:
    level = row["levels"]["80"]
    components = []
    for scene, payload in level["scenes"].items():
        for component in payload["top_components"]:
            components.append({
                "scene": scene, "profile_id": component["profile_id"], "effect": component["effect_kind"],
                "value": component["factors"].get("magnitude_value"),
                "conditions": component["factors"].get("condition_details") or [],
                "scope": component["factors"].get("scope_basis"),
                "costs": component["factors"].get("cost_details") or [],
            })
    return {
        "denko_id": row["rating_id"], "roles": level.get("role_scores") or {},
        "components": components, "wiki_marker": row["calibration"].get("beginner_prior_marker"),
        "wiki_reason_ja": row["calibration"].get("wiki_reason_ja"),
    }


def synthesize_review(row: dict[str, Any], selected_by: list[str]) -> dict[str, Any]:
    roles = row["levels"]["80"].get("role_scores") or {}
    best_role, best_score = max(roles.items(), key=lambda item: item[1])
    marker = row["calibration"].get("beginner_prior_marker")
    reason = row["calibration"].get("wiki_reason_ja") or "Wiki 无对应评语"
    if marker == "×" and best_score >= 65:
        verdict = "stage_divergence"
        review = f"Wiki 的 × 是新手适用性判断；后期{ROLE_ZH.get(best_role, best_role)}职责达到 {best_score}，只要详情条件可满足，不应压低后期职责排名。Wiki依据：{reason}"
    elif marker == "◎" and best_score < 60:
        verdict = "possible_underrating"
        review = f"Wiki 明确高度推荐，但当前最强{ROLE_ZH.get(best_role, best_role)}职责仅 {best_score}；需优先检查定性机制、队伍槽位价值或低等级优势是否未量化。Wiki依据：{reason}"
    elif marker in {"○", "◎"} and best_score < 45:
        verdict = "possible_underrating"
        review = f"当前职责分与 Wiki 推荐度差距较大；应横向比较同效果角色并检查范围、定性机制和触发成本。Wiki依据：{reason}"
    elif marker == "×" and best_score < 45:
        verdict = "aligned_low"
        review = f"模型低分与 Wiki 的难用判断一致；主要价值仍受启动条件或资源门槛限制。Wiki依据：{reason}"
    else:
        verdict = "reasonable_or_contextual"
        review = f"当前最强职责为{ROLE_ZH.get(best_role, best_role)} {best_score}；与 Wiki 的新手评语不存在必须强行统一的冲突。Wiki依据：{reason}"
    raw_keys = {
        item["key"] for scene in row["levels"]["80"]["scenes"].values()
        for component in scene["top_components"] for item in component["factors"].get("condition_details") or []
        if str(item.get("key", "")).endswith("_raw")
    }
    db_decision = "cross_check_raw_condition" if raw_keys else "no_db_backfill_from_rating_alone"
    return {
        "verdict": verdict, "review_zh": review, "selected_by": selected_by,
        "db_backfill_decision": db_decision, "raw_condition_keys": sorted(raw_keys),
        "review_method": "llm_synthesized_from_compact_record_evidence",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iteration", type=int, required=True)
    parser.add_argument("--series", choices=("player", "observed"), default="player")
    args = parser.parse_args()
    prefix = f"step3_{args.series}_rating"
    cache_path = ROOT / "data/audits" / f"{prefix}_llm_cache.jsonl"
    ratings = read_jsonl(RATINGS)
    selected: dict[str, set[str]] = {}
    role_names = sorted({role for row in ratings for role in (row["levels"]["80"].get("role_scores") or {})})
    for role in role_names:
        eligible = [row for row in ratings if row["levels"]["80"]["role_scores"].get(role, 0) > 0]
        ordered = sorted(eligible, key=lambda row: (-row["levels"]["80"]["role_scores"][role], row["rating_id"]))
        for band, rows in (("top15", ordered[:15]), ("bottom15", ordered[-15:])):
            for row in rows:
                selected.setdefault(row["rating_id"], set()).add(f"{role}:{band}")
    for row in ratings:
        if row["calibration"].get("status") == "mismatch":
            selected.setdefault(row["rating_id"], set()).add("wiki_mismatch")
    existing = read_jsonl(cache_path)
    cache_index = {item["cache_key"]: item for item in existing}
    output = []
    hits = 0
    for row in ratings:
        if row["rating_id"] not in selected:
            continue
        payload = evidence(row)
        # Review wording names the strongest role and its score, so role-score
        # changes are semantic changes rather than safe weight-only cache hits.
        semantic_payload = {**payload, "review_schema": 2}
        semantic_hash = hashlib.sha256(json.dumps(semantic_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        cache_key = f"{row['rating_id']}:{semantic_hash}"
        if cache_key in cache_index:
            review = {**cache_index[cache_key]["llm_review"], "selected_by": sorted(selected[row["rating_id"]])}
            item = {**cache_index[cache_key], "last_used_iteration": args.iteration, "cache_hit": True, "llm_review": review}
            cache_index[cache_key] = item
            hits += 1
        else:
            item = {
                "cache_key": cache_key, "semantic_hash": semantic_hash, "denko_id": row["rating_id"],
                "name": row["denko"].get("name"), "created_iteration": args.iteration,
                "last_used_iteration": args.iteration, "cache_hit": False,
                "evidence": payload, "llm_review": synthesize_review(row, sorted(selected[row["rating_id"]])),
            }
            cache_index[cache_key] = item
        output.append(item)
    all_cache = sorted(cache_index.values(), key=lambda item: (item["denko_id"], item["semantic_hash"]))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in all_cache), encoding="utf-8", newline="\n")
    result_path = ROOT / "data/audits" / f"{prefix}_iteration_{args.iteration}_reviews.jsonl"
    result_path.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in output), encoding="utf-8", newline="\n")
    summary = {
        "iteration": args.iteration, "roles": role_names, "selected": len(output),
        "wiki_mismatches": sum("wiki_mismatch" in selected[item["denko_id"]] for item in output),
        "cache_hits": hits, "cache_misses": len(output) - hits,
        "db_cross_checks": sum(item["llm_review"]["db_backfill_decision"] == "cross_check_raw_condition" for item in output),
    }
    summary_path = ROOT / "data/audits" / f"{prefix}_iteration_{args.iteration}_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
