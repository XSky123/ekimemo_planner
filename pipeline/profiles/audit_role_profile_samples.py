from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
PROFILES = ROOT / "data" / "role_profiles" / "role_profiles.jsonl"
OUT = ROOT / "data" / "audits" / "step3_role_profile_sample_audit.json"
SEED = 20260711


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def has_scene(profile: dict[str, Any], scene: str) -> bool:
    return scene in {tag["id"] for tag in profile.get("scene_tags") or []}


def inspect(profile: dict[str, Any], stratum: str) -> dict[str, Any]:
    component = profile["component"]
    excluded = profile["solver_eligibility"]["status"] == "excluded"
    passed = bool(component["source"].get("condition_raw") or component.get("level_values") or excluded) and bool(component.get("recipient") or excluded)
    return {
        "stratum": stratum,
        "profile_id": profile["profile_id"],
        "effect_kind": component["effect_kind"],
        "recipient": component.get("recipient") or [],
        "access_direction": component.get("access_direction") or [],
        "activation_mode": profile["activation"]["mode"],
        "availability": component.get("availability") or {},
        "scene_tags": [tag["id"] for tag in profile.get("scene_tags") or []],
        "review_reasons": profile["record_meta"].get("review_reasons") or [],
        "passed": passed,
    }


def choose(rng: random.Random, profiles: list[dict[str, Any]], stratum: str, predicate: Callable[[dict[str, Any]], bool]) -> dict[str, Any]:
    clean = [profile for profile in profiles if predicate(profile) and not profile["record_meta"].get("needs_review")]
    if not clean:
        raise RuntimeError(f"no non-review profile available for {stratum}")
    return inspect(rng.choice(clean), stratum)


def main() -> int:
    profiles = read_jsonl(PROFILES)
    rng = random.Random(SEED)
    samples = [
        choose(rng, profiles, scene, lambda profile, scene=scene: has_scene(profile, scene))
        for scene in ["capture", "defense", "commute", "expedition", "visit_count_event", "score_exp", "growth", "mechanism"]
    ]
    samples.extend([
        choose(rng, profiles, "manual", lambda profile: profile["activation"]["mode"] == "manual"),
        choose(rng, profiles, "probability", lambda profile: "probabilistic" in profile["constraints"].get("opportunity_costs", [])),
        choose(rng, profiles, "vu", lambda profile: bool((profile["component"].get("availability") or {}).get("vu_only"))),
    ])
    result = {
        "artifact": "step3_role_profile_sample_audit",
        "seed": SEED,
        "sample_count": len(samples),
        "issue_count": sum(not sample["passed"] for sample in samples),
        "samples": samples,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"sample_count": len(samples), "issue_count": result["issue_count"]}, ensure_ascii=False))
    return 1 if result["issue_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
