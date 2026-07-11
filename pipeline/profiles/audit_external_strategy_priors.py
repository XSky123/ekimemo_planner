from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROFILES = ROOT / "data" / "role_profiles" / "role_profiles.jsonl"
SOURCES = ROOT / "data" / "reference_priors" / "external_strategy_sources.json"
OUT = ROOT / "data" / "audits" / "step3_external_strategy_prior_audit.json"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    profiles = read_jsonl(PROFILES)
    sources = json.loads(SOURCES.read_text(encoding="utf-8"))
    required_top_level = ["component", "activation", "constraints", "scene_tags", "solver_eligibility"]
    missing_top_level = [profile["profile_id"] for profile in profiles if any(key not in profile for key in required_top_level)]
    scenes = Counter(tag["id"] for profile in profiles for tag in profile.get("scene_tags") or [])
    costs = Counter(cost for profile in profiles for cost in profile["constraints"].get("opportunity_costs") or [])
    effect_kinds = Counter(profile["component"]["effect_kind"] for profile in profiles)
    expected_scene_tags = {"capture", "defense", "score_exp", "growth"}
    expected_costs = {"manual_activation", "probabilistic", "context_or_formation_constraint", "vu_dependency", "self_debuff"}
    expected_defense_channels = {"damage_reduction", "hp_recovery", "damage_substitution", "activation_probability_boost"}
    checks = [
        {"id": "reusable_profile_fields", "passed": not missing_top_level, "reason_zh": "每个组件都有独立的效果、发动、约束、场景与可求解状态。", "sample": missing_top_level[:10]},
        {"id": "goal_first_scene_projection", "passed": expected_scene_tags <= set(scenes), "reason_zh": "外部编成文章强调先选目标；画像层已保留攻、防、积分/经验与成长的独立场景。", "missing": sorted(expected_scene_tags - set(scenes))},
        {"id": "condition_cost_model", "passed": expected_costs <= set(costs), "reason_zh": "低概率、手动、统一属性/VU 与自损不会被当作无条件强度。", "missing": sorted(expected_costs - set(costs))},
        {"id": "defense_synergy_channels", "passed": expected_defense_channels <= set(effect_kinds), "reason_zh": "防守链可分别读取概率操作、承伤/减伤、回复与无效化相关组件。", "missing": sorted(expected_defense_channels - set(effect_kinds))},
        {"id": "no_article_fact_override", "passed": all(source["updated_through"] == "2025-05-07" for source in sources["sources"]), "reason_zh": "外部文章已停止更新，因此只作为先验/契约校验，不覆盖详情页事实。"},
    ]
    result = {
        "artifact": "step3_external_strategy_prior_audit",
        "source_authority": "recommendation_prior",
        "sources": [{"source_id": item["source_id"], "url": item["url"], "updated_through": item["updated_through"]} for item in sources["sources"]],
        "profile_count": len(profiles),
        "checks": checks,
        "issue_count": sum(not check["passed"] for check in checks),
        "caveat_zh": "这是对画像建模维度的双重校验，不是把旧策略文章的角色排名写回当前 DB。",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"checks": len(checks), "issue_count": result["issue_count"]}, ensure_ascii=False))
    return 1 if result["issue_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
