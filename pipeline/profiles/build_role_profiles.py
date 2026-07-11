from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SKILL_PATH = ROOT / "data" / "step1_db" / "skill_facts.jsonl"
DENKO_PATH = ROOT / "data" / "step1_db" / "denko_facts.jsonl"
OUT_DIR = ROOT / "data" / "role_profiles"
OUT_PATH = OUT_DIR / "role_profiles.jsonl"
MANIFEST_PATH = OUT_DIR / "manifest.json"
VALIDATION_PATH = OUT_DIR / "validation.json"
REVIEW_QUEUE_PATH = ROOT / "data" / "review_queue" / "step3_role_profile_review.jsonl"
PROFILE_VERSION = "role_profile.v1"
JST = timezone(timedelta(hours=9))


EFFECT_CHANNELS = {
    "atk_buff": "offense", "ap_buff": "offense", "fixed_damage": "offense",
    "additional_fixed_damage": "offense", "def_debuff": "offense", "atk_debuff": "defense",
    "def_buff": "defense", "damage_reduction": "defense", "hp_recovery": "defense",
    "hp_recovery_bonus": "defense", "survive_hp1": "defense", "damage_nullification": "defense",
    "damage_cap": "defense", "damage_substitution": "defense", "link_continue": "defense",
    "link_retention": "defense", "counter": "defense", "counter_damage": "defense",
    "reboot": "defense", "exp_gain": "economy", "exp_distribution": "economy",
    "exp_distribution_bonus": "economy", "score_gain": "economy", "additional_score_gain": "economy",
    "score_random_modifier": "economy", "match_bonus": "economy", "mile_gain": "economy",
    "today_new_station_bonus": "economy", "item_gain": "economy", "extra_access": "mobility",
    "random_previous_station_access": "mobility", "remote_station_access": "mobility",
    "station_link_transfer": "mobility", "link_transfer": "mobility", "radar_detection_range": "mobility",
    "radar_max_detection_range": "mobility", "memory_access_station_count": "mobility",
    "memory_access_time": "mobility", "skill_disable": "disruption",
    "skill_effect_nullification": "disruption", "skill_force_end": "disruption",
    "battery_disable": "disruption", "footbar": "disruption", "force_hp_zero": "disruption",
    "activation_probability_boost": "mechanism", "cooldown_reduction": "mechanism",
    "cooldown_reset": "mechanism", "cooldown_entry": "mechanism", "duration_extension": "mechanism",
    "effect_multiplier": "mechanism", "film_effect_multiplier": "mechanism",
    "film_series_effect_boost": "mechanism", "friend_slot_increase": "utility",
    "skill_continue": "utility", "link_bonus": "utility", "link_bonus_zero": "utility",
    "def_modifier": "defense", "ap_debuff": "disruption", "none": "unknown",
}

SELF_DEBUFF_KINDS = {"battery_disable", "skill_force_end", "force_hp_zero", "cooldown_entry"}
CAPTURE_KINDS = {"atk_buff", "ap_buff", "fixed_damage", "additional_fixed_damage", "def_debuff", "force_hp_zero"}
DEFENSE_KINDS = {"def_buff", "atk_debuff", "damage_reduction", "hp_recovery", "hp_recovery_bonus", "survive_hp1", "damage_nullification", "damage_cap", "damage_substitution", "link_continue", "link_retention", "counter", "counter_damage", "reboot", "link_transfer", "station_link_transfer"}
EXPEDITION_KINDS = {"extra_access", "random_previous_station_access", "remote_station_access", "station_link_transfer", "link_transfer", "radar_detection_range", "radar_max_detection_range", "link_bonus", "memory_access_station_count", "memory_access_time"}
VISIT_EVENT_KINDS = {"extra_access", "random_previous_station_access", "remote_station_access", "station_link_transfer", "link_transfer"}
ECONOMY_KINDS = {"exp_gain", "exp_distribution", "exp_distribution_bonus", "score_gain", "additional_score_gain", "score_random_modifier", "match_bonus", "mile_gain", "today_new_station_bonus", "item_gain"}
GROWTH_KINDS = {"exp_gain", "exp_distribution", "exp_distribution_bonus", "match_bonus"}
MECHANISM_KINDS = {
    "skill_disable", "skill_effect_nullification", "skill_force_end", "battery_disable", "footbar", "force_hp_zero",
    "activation_probability_boost", "cooldown_reduction", "cooldown_reset", "cooldown_entry", "duration_extension",
    "effect_multiplier", "film_effect_multiplier", "film_series_effect_boost", "skill_continue",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_text_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.replace("\r\n", "\n").replace("\r", "\n"), encoding="utf-8", newline="\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_percent(raw: Any) -> dict[str, Any]:
    text = str(raw or "").strip()
    # A hyphen after a percent sign is a range separator ("0.7%-70%"), not a
    # negative percentage. The lookbehind lets the second number be parsed as 70.
    matches = re.findall(r"(?<![%％])(-?\d+(?:\.\d+)?)\s*[%％]", text)
    values = [float(value) for value in matches]
    unique = sorted(set(values))
    range_like = bool(re.search(r"[%％]\s*(?:[-〜～]|\u2013)\s*\d+(?:\.\d+)?\s*[%％]", text))
    if len(unique) == 2 and range_like:
        return {
            "raw": text or None,
            "percent": None,
            "min_percent": unique[0],
            "max_percent": unique[1],
            "parse_status": "range",
        }
    return {
        "raw": text or None,
        "percent": unique[0] if len(unique) == 1 else None,
        "min_percent": None,
        "max_percent": None,
        "parse_status": "exact" if len(unique) == 1 else ("missing" if not values else "ambiguous"),
    }


def parse_seconds(raw: Any) -> dict[str, Any]:
    text = str(raw or "").strip()
    if text in {"なし", "無し", "0分", "0 分"}:
        return {"raw": text, "seconds": 0, "parse_status": "exact"}
    hours = re.search(r"(\d+(?:\.\d+)?)\s*時間", text)
    minutes = re.search(r"(\d+(?:\.\d+)?)\s*分", text)
    seconds = None
    if hours or minutes:
        seconds = int(round((float(hours.group(1)) * 3600 if hours else 0) + (float(minutes.group(1)) * 60 if minutes else 0)))
    return {"raw": text or None, "seconds": seconds, "parse_status": "exact" if seconds is not None else ("missing" if not text or text == "-" else "unparsed")}


def activation_mode(raw: Any, component: dict[str, Any]) -> str:
    text = str(raw or "")
    if "手動" in text or (component.get("trigger_conditions") or {}).get("event") == "manual_activation":
        return "manual"
    if "常時" in text:
        return "always"
    if text:
        return "auto"
    return "unknown"


def trigger_actor(component: dict[str, Any]) -> str:
    conditions = component.get("trigger_conditions") or {}
    actor = conditions.get("actor_scope")
    if actor:
        return str(actor)
    values = set(access_directions(component))
    if values & {"both"}:
        return "either_accessing_or_accessed_denko"
    if values & {"own_team_link"}:
        return "any_team_member"
    if "active" in values or "outgoing" in values:
        return "accessing_denko"
    if "received" in values or "passive" in values:
        return "accessed_denko"
    return "unknown"


def access_directions(component: dict[str, Any]) -> list[str]:
    conditions = component.get("trigger_conditions") or {}
    values = conditions.get("access_directions") or []
    if not isinstance(values, list):
        values = [values]
    if conditions.get("access_direction"):
        values.append(conditions["access_direction"])
    event = str(conditions.get("event") or conditions.get("event_hint") or "")
    event_direction = {
        "access": "active",
        "accessed": "passive",
        "access_or_accessed": "both",
        "link": "own_team_link",
        "link_failure": "active",
        "remote_access": "active",
    }.get(event)
    if event_direction:
        values.append(event_direction)
    return sorted({str(value) for value in values if value})


def level_values(component: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    values: dict[str, Any] = {}
    probabilities: dict[str, Any] = {}
    durations: dict[str, Any] = {}
    cooldowns: dict[str, Any] = {}
    for level, raw in sorted((component.get("values_by_denko_level") or {}).items(), key=lambda item: int(item[0]) if str(item[0]).isdigit() else 999):
        probability_values = raw.get("probability") or {}
        if not isinstance(probability_values, dict):
            probability_values = {"activation_probability": probability_values}
        parsed_probabilities = {str(key): parse_percent(value) for key, value in probability_values.items() if value not in (None, "", "-")}
        exact_values = [item["percent"] for item in parsed_probabilities.values() if item["parse_status"] == "exact"]
        range_values = [item for item in parsed_probabilities.values() if item["parse_status"] == "range"]
        has_precomputed_branch_expectation = raw.get("value_expected") is not None and len(parsed_probabilities) > 1
        top_status = "exact" if len(exact_values) == 1 and len(parsed_probabilities) == 1 else ("range" if len(range_values) == 1 and len(parsed_probabilities) == 1 else ("missing" if not parsed_probabilities else ("branch_expected" if has_precomputed_branch_expectation else "ambiguous")))
        probabilities[str(level)] = {
            "raw": probability_values or None,
            "percent": exact_values[0] if len(set(exact_values)) == 1 and len(exact_values) == 1 else None,
            "min_percent": range_values[0]["min_percent"] if top_status == "range" else None,
            "max_percent": range_values[0]["max_percent"] if top_status == "range" else None,
            "details": parsed_probabilities,
            "parse_status": top_status,
        }
        duration = parse_seconds(raw.get("duration"))
        cooldown = parse_seconds(raw.get("cooldown"))
        durations[str(level)] = duration
        cooldowns[str(level)] = cooldown
        values[str(level)] = {
            "value_raw": raw.get("value_raw"),
            "value_numeric": raw.get("value_numeric"),
            "value_min": raw.get("value_min"),
            "value_max": raw.get("value_max"),
            "value_expected": raw.get("value_expected"),
            "value_expected_multiplier": raw.get("value_expected_multiplier"),
            "options": raw.get("options"),
            "unit": raw.get("unit"),
            "source_text": raw.get("source_text"),
        }
    return values, probabilities, durations, cooldowns


def uptime_by_level(durations: dict[str, Any], cooldowns: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for level, duration in durations.items():
        cooldown = cooldowns.get(level) or {}
        duration_seconds = duration.get("seconds")
        cooldown_seconds = cooldown.get("seconds")
        if duration_seconds is None or cooldown_seconds is None:
            result[level] = {"ratio": None, "status": "unknown", "reason": "duration_or_cooldown_unparsed"}
            continue
        result[level] = {
            "ratio": round(duration_seconds / (duration_seconds + cooldown_seconds), 6),
            "status": "estimated",
            "formula": "duration / (duration + cooldown)",
            "assumption": "conservative_cycle_estimate",
        }
    return result


def hard_constraints(component: dict[str, Any]) -> list[dict[str, Any]]:
    filters = component.get("target_filters") or {}
    triggers = component.get("trigger_conditions") or {}
    hard: list[dict[str, Any]] = []
    for key, value in filters.items():
        if value not in (None, "", [], {}):
            hard.append({"source": "target_filters", "key": key, "value": value})
    for key, value in triggers.items():
        if key in {"access_direction", "access_directions", "actor_scope", "event_hint", "event"}:
            continue
        if value not in (None, "", [], {}):
            hard.append({"source": "trigger_conditions", "key": key, "value": value})
    present_keys = {str(item["key"]) for item in hard}
    raw_text = " ".join(str(component.get(key) or "") for key in ("condition_raw", "remarks_raw"))
    # Detail-page rows occasionally retain a condition only in Japanese prose.
    # These compact hints make it usable for Step3 while retaining the raw source.
    if "weather" not in present_keys:
        weather_terms = {"晴れ": "sunny", "雨": "rain", "雪": "snow", "くもり": "cloudy", "曇り": "cloudy"}
        matched_weather = sorted({value for term, value in weather_terms.items() if term in raw_text})
        if matched_weather:
            hard.append({"source": "condition_raw_inference", "key": "weather", "value": matched_weather, "raw": raw_text})
    if "weekday" not in present_keys and any(day in raw_text for day in ("月曜", "火曜", "水曜", "木曜", "金曜", "土曜", "日曜")):
        hard.append({"source": "condition_raw_inference", "key": "weekday", "value": "see_raw", "raw": raw_text})
    if "season_months" not in present_keys and (any(token in raw_text for token in ("春", "夏", "秋", "冬")) or re.search(r"(?:1[0-2]|[1-9])月", raw_text)):
        hard.append({"source": "condition_raw_inference", "key": "season_or_month", "value": "see_raw", "raw": raw_text})
    directions = set(access_directions(component))
    if "own_team_link" in directions and not ({"requires_link_success", "requires_skill_holder_link_success"} & present_keys):
        hard.append({"source": "trigger_conditions", "key": "requires_link_success", "value": True})
    return hard


def opportunity_costs(component: dict[str, Any], activation: dict[str, Any], hard: list[dict[str, Any]]) -> list[str]:
    costs: list[str] = []
    if activation["mode"] == "manual":
        costs.append("manual_activation")
    if activation["mode"] == "auto" and any(item.get("percent") not in (None, 100.0) for item in activation["probability_by_level"].values()):
        costs.append("probabilistic")
    if (component.get("availability") or {}).get("vu_only"):
        costs.append("vu_dependency")
    cooldown_values = [item.get("seconds") for item in activation["cooldown_by_level"].values() if item.get("seconds") is not None]
    if cooldown_values and min(cooldown_values) >= 4 * 3600:
        costs.append("long_cooldown")
    constraint_keys = {item["key"] for item in hard}
    if constraint_keys & {"attribute", "attributes", "type", "own_team_all_attribute", "formation_only", "position_relative_to_self", "relative_position", "own_team_type", "opponent_type", "opponent_attribute", "weather", "temperature_band", "time_window", "season_months", "weekday"}:
        costs.append("context_or_formation_constraint")
    return costs


def self_debuff(component: dict[str, Any]) -> list[dict[str, Any]]:
    effect_kind = component.get("effect_kind")
    targets = set(component.get("target_scope") or [])
    if effect_kind in SELF_DEBUFF_KINDS or (effect_kind in {"atk_debuff", "def_debuff", "ap_debuff"} and targets & {"self", "team_all", "own_team"}):
        return [{"effect_kind": effect_kind, "target_scope": sorted(targets), "condition_raw": component.get("condition_raw")}]
    filters = component.get("target_filters") or {}
    raw = filters.get("paired_self_debuff_raw")
    return [{"effect_kind": "paired_self_debuff", "target_scope": ["self"], "condition_raw": raw}] if raw else []


def scene_tags(component: dict[str, Any], activation: dict[str, Any]) -> list[dict[str, Any]]:
    kind = str(component.get("effect_kind") or "none")
    targets = set(component.get("target_scope") or [])
    own_side_debuff = kind in {"atk_debuff", "def_debuff", "ap_debuff"} and bool(targets & {"self", "team_all", "own_team"})
    tags: list[dict[str, Any]] = []
    def add(identifier: str, reason: str, confidence: str = "high") -> None:
        tags.append({"id": identifier, "confidence": confidence, "reasons_zh": [reason]})
    if kind == "none":
        add("unclassified", "详情页尚未提取到可用效果；该组件不参与场景候选", "low")
        return tags
    if kind in CAPTURE_KINDS and not own_side_debuff:
        add("capture", "该组件直接提高抢站/突破时的攻击或削弱对手防御能力")
    if kind in DEFENSE_KINDS and not own_side_debuff:
        add("defense", "该组件直接提高守站、生存、减伤或 link 保持能力")
    if kind in EXPEDITION_KINDS:
        add("expedition", "该组件与远距离、额外访问、站点转移或探测范围有关")
    if kind in VISIT_EVENT_KINDS:
        add("visit_count_event", "该组件可能直接增加或扩展一次访问机会")
    if kind in ECONOMY_KINDS:
        add("score_exp", "该组件直接影响积分、经验、里程或物品收益")
    if kind in GROWTH_KINDS:
        add("growth", "该组件与经验获取或经验分配有关")
    if kind in MECHANISM_KINDS:
        add("mechanism", "该组件改变技能发动、无效化、持续或冷却关系，需要结合队伍上下文判断")
    if not own_side_debuff and activation["mode"] in {"always", "auto"} and "manual_activation" not in opportunity_costs(component, activation, hard_constraints(component)):
        add("commute", "无需每次手动操作即可在通勤中生效", "medium")
    if not tags:
        add("mechanism", "该组件主要改变技能机制或干扰关系，需要结合队伍上下文判断", "medium")
    return tags


def denko_metadata() -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for row in read_jsonl(DENKO_PATH):
        identity = row.get("identity") or {}
        denko_id = str(identity.get("denko_id") or row.get("denko_id"))
        metadata[denko_id] = {
            "attribute": identity.get("attribute"),
            "type": identity.get("type"),
        }
    return metadata


def build_profile(skill: dict[str, Any], component: dict[str, Any], metadata: dict[str, dict[str, Any]]) -> dict[str, Any]:
    denko_id = str(skill["denko_id"])
    component_id = str(component["component_id"])
    source_meta = skill.get("record_meta") or {}
    component_meta_reasons = component.get("review_reasons") or []
    values, probabilities, durations, cooldowns = level_values(component)
    raw_activation = component.get("activation_type") or skill.get("activation_type")
    activation = {
        "mode": activation_mode(raw_activation, component),
        "raw_activation_type": raw_activation,
        "probability_by_level": probabilities,
        "duration_by_level": durations,
        "cooldown_by_level": cooldowns,
        "uptime_by_level": uptime_by_level(durations, cooldowns),
    }
    hard = hard_constraints(component)
    self_costs = self_debuff(component)
    costs = opportunity_costs(component, activation, hard)
    if self_costs:
        costs.append("self_debuff")
    effect_kind = str(component.get("effect_kind") or "none")
    excluded = effect_kind == "none"
    if excluded:
        eligibility = {"status": "excluded", "reason": "effect_kind_none"}
    elif self_costs and not component.get("target_scope"):
        eligibility = {"status": "not_standalone", "reason": "self_debuff_or_cost_component"}
    elif hard or costs:
        eligibility = {"status": "conditional", "reason": "requires_context_or_has_opportunity_cost"}
    else:
        eligibility = {"status": "eligible", "reason": "direct_reusable_component"}
    component_confidence = str(component.get("confidence") or source_meta.get("confidence") or "low")
    # Step1 review flags include historic batch-level semantic review notes. Preserve
    # them in provenance, but queue only anomalies that prevent reliable Step3 use.
    review_reasons: list[str] = []
    if effect_kind not in EFFECT_CHANNELS:
        review_reasons.append("unknown_effect_channel")
    if effect_kind != "none" and not component.get("target_scope"):
        review_reasons.append("missing_recipient")
    dynamic_value = (component.get("scaling_conditions") or {}).get("fixed_numeric_value_status") == "dynamic_by_film_effect"
    if not values and effect_kind != "none" and not dynamic_value and not (component.get("availability") or {}).get("vu_only"):
        review_reasons.append("missing_level_values")
    # VU tables often describe a base probability together with a capped bonus,
    # a fallback branch, or a symbolic x%. Preserve those raw branches without
    # treating them as a parser failure. Non-VU ambiguity still needs review.
    if any(
        level not in {"92", "96", "100"} and item.get("parse_status") == "ambiguous"
        for level, item in probabilities.items()
    ):
        review_reasons.append("ambiguous_probability_range_or_branches")
    if "screenshot_needed" in component_meta_reasons and not (component.get("availability") or {}).get("vu_only"):
        review_reasons.append("screenshot_needed")
    if "new_effect_kind_needs_solver_model" in component_meta_reasons and effect_kind not in EFFECT_CHANNELS:
        review_reasons.append("new_effect_kind_needs_solver_model")
    review_reasons = list(dict.fromkeys(review_reasons))
    needs_review = bool(review_reasons)
    return {
        "profile_id": f"{denko_id}#{component_id}",
        "profile_version": PROFILE_VERSION,
        "record_meta": {
            "source_url": source_meta.get("source_url") or skill.get("detail_url"),
            "source_authority": "detail_page",
            "content_hash": hashlib.sha256(json.dumps(component, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest(),
            "parser_version": PROFILE_VERSION,
            "parsed_at": datetime.now(JST).isoformat(),
            "confidence": component_confidence,
            "needs_review": needs_review,
            "review_reasons": list(dict.fromkeys(review_reasons)),
            "derived_from": {
                "skill_fact_content_hash": source_meta.get("content_hash"),
                "component_id": component_id,
                "manual_patch_ids": list(dict.fromkeys([*(source_meta.get("manual_patch_ids") or []), *(component.get("manual_patch_ids") or [])])),
                "db_backfill_lock": bool(component.get("db_backfill_lock")),
                "source_record_needs_review": bool(source_meta.get("needs_review")),
                "source_record_review_reasons": source_meta.get("review_reasons") or [],
            },
        },
        "denko": {
            "denko_id": denko_id,
            "name": skill.get("name"),
            "pool": skill.get("pool"),
            "attribute": (metadata.get(denko_id) or {}).get("attribute"),
            "type": (metadata.get(denko_id) or {}).get("type"),
            "key_level_stats": skill.get("key_level_stats") or {},
        },
        "component": {
            "component_id": component_id,
            "effect_kind": effect_kind,
            "effect_channel": EFFECT_CHANNELS.get(effect_kind, "unknown"),
            "effect_role": component.get("effect_role"),
            "recipient": component.get("target_scope") or [],
            "target_filters": component.get("target_filters") or {},
            "trigger_conditions": component.get("trigger_conditions") or {},
            "trigger_actor": trigger_actor(component),
            "access_direction": access_directions(component),
            "availability": component.get("availability") or {},
            "level_values": values,
            "source": {
                "condition_label": component.get("condition_label"),
                "condition_raw": component.get("condition_raw"),
                "remarks_raw": component.get("remarks_raw"),
            },
        },
        "activation": activation,
        "constraints": {"hard": hard, "opportunity_costs": sorted(set(costs)), "self_debuff": self_costs},
        "scene_tags": scene_tags(component, activation),
        "solver_eligibility": eligibility,
    }


def validate(profiles: list[dict[str, Any]], source_components: list[tuple[str, str]]) -> dict[str, Any]:
    profile_ids = [str(profile["profile_id"]) for profile in profiles]
    expected_ids = [f"{denko_id}#{component_id}" for denko_id, component_id in source_components]
    duplicates = sorted([item for item, count in Counter(profile_ids).items() if count > 1])
    missing = sorted(set(expected_ids) - set(profile_ids))
    unexpected = sorted(set(profile_ids) - set(expected_ids))
    missing_recipient = [
        profile["profile_id"]
        for profile in profiles
        if not profile["component"]["recipient"] and profile["solver_eligibility"]["status"] != "excluded"
    ]
    unknown_direction = [profile["profile_id"] for profile in profiles if not profile["component"]["access_direction"]]
    invalid_uptime = []
    for profile in profiles:
        for level, uptime in profile["activation"]["uptime_by_level"].items():
            ratio = uptime.get("ratio")
            if ratio is not None and not 0 <= ratio <= 1:
                invalid_uptime.append(f"{profile['profile_id']}@{level}")
    issues = []
    if duplicates:
        issues.append({"kind": "duplicate_profile_id", "count": len(duplicates), "sample": duplicates[:20]})
    if missing:
        issues.append({"kind": "missing_component_profile", "count": len(missing), "sample": missing[:20]})
    if unexpected:
        issues.append({"kind": "unexpected_profile", "count": len(unexpected), "sample": unexpected[:20]})
    if invalid_uptime:
        issues.append({"kind": "invalid_uptime", "count": len(invalid_uptime), "sample": invalid_uptime[:20]})
    return {
        "artifact": "role_profiles",
        "profile_version": PROFILE_VERSION,
        "counts": {
            "source_components": len(source_components),
            "profiles": len(profiles),
            "excluded": sum(profile["solver_eligibility"]["status"] == "excluded" for profile in profiles),
            "conditional": sum(profile["solver_eligibility"]["status"] == "conditional" for profile in profiles),
            "needs_review": sum(profile["record_meta"]["needs_review"] for profile in profiles),
            "missing_recipient_info": len(missing_recipient),
            "unknown_access_direction_info": len(unknown_direction),
        },
        "issue_count": len(issues),
        "issues": issues,
        "informational_samples": {
            "missing_recipient": missing_recipient[:20],
            "unknown_access_direction": unknown_direction[:20],
        },
    }


def review_queue_rows(profiles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for profile in profiles:
        meta = profile["record_meta"]
        if not meta.get("needs_review"):
            continue
        component = profile["component"]
        values = component.get("level_values") or {}
        rows.append({
            "queue_id": profile["profile_id"],
            "source_authority": "detail_page",
            "source_url": meta.get("source_url"),
            "content_hash": meta.get("content_hash"),
            "profile_version": PROFILE_VERSION,
            "review_reasons": meta.get("review_reasons") or [],
            "denko": {key: profile["denko"].get(key) for key in ("denko_id", "name", "pool", "attribute", "type")},
            "component": {
                "component_id": component["component_id"],
                "effect_kind": component["effect_kind"],
                "recipient": component.get("recipient") or [],
                "target_filters": component.get("target_filters") or {},
                "trigger_conditions": component.get("trigger_conditions") or {},
                "condition_raw": component["source"].get("condition_raw"),
                "remarks_raw": component["source"].get("remarks_raw"),
                "lv30": values.get("30"),
                "lv50": values.get("50"),
                "lv80": values.get("80"),
            },
            "review_status": "pending_auto_or_targeted_review",
        })
    return rows


def main() -> None:
    skills = read_jsonl(SKILL_PATH)
    metadata = denko_metadata()
    source_components: list[tuple[str, str]] = []
    profiles: list[dict[str, Any]] = []
    for skill in skills:
        for component in skill.get("skill_components") or []:
            source_components.append((str(skill["denko_id"]), str(component["component_id"])))
            profiles.append(build_profile(skill, component, metadata))
    profiles.sort(key=lambda item: item["profile_id"])
    validation = validate(profiles, source_components)
    review_rows = review_queue_rows(profiles)
    validation["review_queue"] = {
        "path": str(REVIEW_QUEUE_PATH.relative_to(ROOT)),
        "count": len(review_rows),
        "by_reason": dict(sorted(Counter(reason for row in review_rows for reason in row["review_reasons"]).items())),
    }
    write_text_lf(OUT_PATH, "".join(json.dumps(profile, ensure_ascii=False, sort_keys=True) + "\n" for profile in profiles))
    write_text_lf(REVIEW_QUEUE_PATH, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in review_rows))
    manifest = {
        "artifact": "role_profiles",
        "profile_version": PROFILE_VERSION,
        "generated_at": datetime.now(JST).isoformat(),
        "source": {"skill_facts": str(SKILL_PATH.relative_to(ROOT)), "content_hash": sha256(SKILL_PATH)},
        "outputs": {"profiles": str(OUT_PATH.relative_to(ROOT)), "validation": str(VALIDATION_PATH.relative_to(ROOT)), "review_queue": str(REVIEW_QUEUE_PATH.relative_to(ROOT))},
        "counts": validation["counts"],
        "generator": str(Path(__file__).relative_to(ROOT)),
        "schema": "schemas/role_profile.schema.json",
    }
    write_text_lf(MANIFEST_PATH, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    write_text_lf(VALIDATION_PATH, json.dumps(validation, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"profiles": len(profiles), "issue_count": validation["issue_count"], "needs_review": validation["counts"]["needs_review"]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
