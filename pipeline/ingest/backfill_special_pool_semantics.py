from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable

import parse as base


ROOT = base.ROOT
RECORD_DIR = ROOT / "data" / "records"
POOLS = {"another", "iks", "ekico", "awamemo"}
BACKFILL_VERSION = "special_pool_semantics.v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )


def number(pattern: str, text: str) -> float | None:
    match = re.search(pattern, base.normalize_numeric_text(text))
    return float(match.group(1)) if match else None


def display_number(value: float | None) -> int | float | None:
    if value is None:
        return None
    numeric = float(value)
    return int(numeric) if numeric.is_integer() else numeric


def value_row(
    fact: dict[str, Any],
    value_raw: str,
    unit: str,
    *,
    value_numeric: float | None = None,
    value_min: float | None = None,
    value_max: float | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    out = {
        "value_raw": value_raw,
        "value_numeric": display_number(value_numeric),
        "unit": unit,
        "probability": base.probability_for_label(fact.get("probability") or {}, label),
        "duration": fact.get("duration"),
        "cooldown": fact.get("cooldown"),
        "skill_level": fact.get("skill_level"),
        "source_text": fact.get("special_explanation"),
        "raw_row": fact.get("raw_row") or {},
    }
    if value_min is not None:
        out["value_min"] = display_number(value_min)
    if value_max is not None:
        out["value_max"] = display_number(value_max)
    return out


ValueBuilder = Callable[[dict[str, Any]], dict[str, Any] | None]


def level_values(row: dict[str, Any], builder: ValueBuilder) -> dict[str, dict[str, Any]]:
    out = {}
    for level, fact in (row.get("values_by_denko_level") or {}).items():
        value = builder(fact)
        if value:
            out[str(level)] = value
    return out


def component(
    row: dict[str, Any],
    component_id: str,
    effect_kind: str,
    builder: ValueBuilder,
    *,
    target_scope: list[str],
    condition_raw: str,
    label: str | None = None,
    role: str | None = None,
    target_filters: dict[str, Any] | None = None,
    trigger_conditions: dict[str, Any] | None = None,
    scaling_conditions: dict[str, Any] | None = None,
    modeling_tags: list[str] | None = None,
    self_debuff_note: str | None = None,
) -> dict[str, Any]:
    values = level_values(row, builder)
    return {
        "component_id": component_id,
        "effect_kind": effect_kind,
        "effect_role": role,
        "condition_label": label,
        "target_scope": target_scope,
        "target_filters": target_filters or {},
        "trigger_conditions": trigger_conditions or {},
        "scaling_conditions": scaling_conditions or {},
        "activation_type": row.get("activation_type"),
        "condition_raw": condition_raw,
        "remarks_raw": row.get("skill_remarks"),
        "values_by_denko_level": values,
        "availability": {"levels": sorted(values, key=int), "vu_only": False},
        "confidence": "high",
        "needs_review": False,
        "review_reasons": ["special_pool_semantic_backfill"],
        "modeling_tags": modeling_tags or [],
        "self_debuff_note": self_debuff_note,
        "db_backfill_lock": True,
        "db_backfill_reason": "详情页特殊模板经语义复查后结构化。",
        "db_backfill_version": BACKFILL_VERSION,
        "source_evidence": {
            "source_url": row.get("detail_url"),
            "source_field": "values_by_denko_level/raw_row",
        },
    }


def condition_value(kind: str, label: str | None = None) -> ValueBuilder:
    return lambda fact: value_row(fact, kind, "condition_only", label=label)


def labeled_numeric(pattern: str, raw_prefix: str, unit: str, label: str | None = None) -> ValueBuilder:
    def build(fact: dict[str, Any]) -> dict[str, Any] | None:
        effect = str(fact.get("effect") or "")
        found = number(pattern, effect)
        if found is None:
            return None
        sign = "" if found < 0 else "+"
        suffix = "%" if "percent" in unit else ""
        return value_row(fact, f"{raw_prefix} {sign}{display_number(found)}{suffix}", unit, value_numeric=found, label=label)

    return build


def components_for(row: dict[str, Any]) -> list[dict[str, Any]]:
    denko_id = str(row.get("denko_id") or "")
    trigger = str(row.get("trigger_condition") or "")

    if denko_id == "another:002":
        def score(fact: dict[str, Any]) -> dict[str, Any] | None:
            value = number(r"スコア獲得\s*(\d+)", str(fact.get("effect") or ""))
            return value_row(fact, f"スコア獲得 {display_number(value)}", "score", value_numeric=value, label="(2)") if value is not None else None

        def end_count(fact: dict[str, Any]) -> dict[str, Any] | None:
            value = number(r"(\d+)回で\s*強制終了", str(fact.get("effect") or ""))
            return value_row(fact, f"{display_number(value)}回で強制終了", "activation_count", value_numeric=value, label="(3)") if value is not None else None

        return [
            component(row, "footbar_1", "footbar", condition_value("フットバース", "(1)"), target_scope=["front_car"], condition_raw="先頭車両の被アクセス時にフットバース", label="(1)", role="default_effect", trigger_conditions={"access_direction": "passive", "event_hint": "accessed"}),
            component(row, "score_gain_2", "score_gain", score, target_scope=["master"], condition_raw="フットバースが発動しなかった場合にスコア獲得", label="(2)", role="additional_effect", trigger_conditions={"access_direction": "passive", "event_hint": "accessed", "requires_component_failure": "footbar_1"}),
            component(row, "skill_force_end_3", "skill_force_end", end_count, target_scope=["own_skill_effects"], condition_raw="フットバース発動回数が上限に達すると強制終了", label="(3)", role="supplemental_effect", trigger_conditions={"basis": "activation_count"}),
        ]

    if denko_id == "another:003":
        return [
            component(row, "def_buff_1", "def_buff", labeled_numeric(r"\(1\)\s*DEF\s*([+-]\d+)%", "DEF", "percent", "(1)"), target_scope=["self"], condition_raw="昼間(6:00～18:00)は自身のDEF増加", label="(1)", role="default_effect", target_filters={"time_window": "daytime"}, trigger_conditions={"time_window_raw": "6:00～18:00"}, self_debuff_note="夜間(18:00～翌6:00)は自身DEF-60%"),
            component(row, "score_gain_2", "score_gain", labeled_numeric(r"\(2\)\s*スコア獲得量\s*([+-]\d+)%", "スコア獲得量", "percent_score", "(2)"), target_scope=["self"], condition_raw="夜間に被アクセスでリブートした時の獲得スコア増加", label="(2)", role="additional_effect", target_filters={"time_window": "nighttime"}, trigger_conditions={"access_direction": "passive", "event_hint": "reboot", "time_window_raw": "18:00～翌6:00"}),
        ]

    if denko_id == "awamemo:000":
        def radar(label_no: int) -> ValueBuilder:
            def build(fact: dict[str, Any]) -> dict[str, Any] | None:
                raw = str((fact.get("raw_row") or {}).get("効果[検知数]") or "")
                value = number(rf"\({label_no}\)\s*\+(\d+)", raw)
                return value_row(fact, f"レーダー検知数 +{display_number(value)}", "station_count", value_numeric=value, label=f"({label_no})") if value is not None else None
            return build

        def radar_max(fact: dict[str, Any]) -> dict[str, Any] | None:
            raw = str((fact.get("raw_row") or {}).get("効果[(2)最大検知数]") or "")
            value = number(r"\+(\d+)", raw)
            return value_row(fact, f"レーダー最大検知数 +{display_number(value)}", "station_count", value_numeric=value, label="(2)") if value is not None else None

        return [
            component(row, "radar_detection_range_1", "radar_detection_range", radar(1), target_scope=["master"], condition_raw="レーダー検知数増加", label="(1)", role="default_effect"),
            component(row, "radar_detection_range_2", "radar_detection_range", radar(2), target_scope=["master"], condition_raw="自身がフェアマスターの場合、レーダー検知数が追加増加", label="(2)", role="additional_effect", target_filters={"requires_fair_master": True}),
            component(row, "radar_max_detection_range_2", "radar_max_detection_range", radar_max, target_scope=["master"], condition_raw="自身がフェアマスターの場合、レーダー最大検知数増加", label="(2)", role="additional_effect", target_filters={"requires_fair_master": True}),
        ]

    if denko_id == "ekico:001":
        return [component(row, "ap_debuff", "ap_debuff", labeled_numeric(r"AP\s*(-\d+)%", "AP", "percent", None), target_scope=["opponent_denko"], condition_raw=trigger, target_filters={"opponent_attribute_differs_from_station": True, "excluded_station_state": "廃駅"}, trigger_conditions={"actor_scope": "any_team_member", "access_direction": "passive", "event_hint": "accessed"})]

    if denko_id == "ekico:002":
        def fixed(pattern: str, prefix: str, label: str) -> ValueBuilder:
            def build(fact: dict[str, Any]) -> dict[str, Any] | None:
                value = number(pattern, str(fact.get("effect") or ""))
                return value_row(fact, f"{prefix} {display_number(value)}", "fixed", value_numeric=value, label=label) if value is not None else None
            return build
        shared = {"minimum_same_attribute_links": 3}
        passive = {"actor_scope": "any_team_member", "access_direction": "passive", "event_hint": "accessed"}
        return [
            component(row, "exp_gain_1", "exp_gain", fixed(r"経験値付与\s*(\d+)", "経験値付与", "(1)"), target_scope=["accessed_denko"], condition_raw="被アクセス時、同属性駅に3駅以上リンクしている場合", label="(1)", role="default_effect", target_filters=shared, trigger_conditions=passive),
            component(row, "score_gain_1", "score_gain", fixed(r"スコア獲得\s*(\d+)", "スコア獲得", "(1)"), target_scope=["master"], condition_raw="被アクセス時、同属性駅に3駅以上リンクしている場合", label="(1)", role="default_effect", target_filters=shared, trigger_conditions=passive),
            component(row, "link_continue_2", "link_continue", condition_value("リンク維持", "(2)"), target_scope=["accessed_denko"], condition_raw="被アクセスでHP0になった時、アクセス駅以外の同属性駅リンクを継続", label="(2)", role="additional_effect", target_filters={"same_attribute_links": True, "exclude_accessed_station": True}, trigger_conditions={"actor_scope": "any_team_member", "access_direction": "passive", "event_hint": "reboot"}),
        ]

    if denko_id == "ekico:003":
        def reduction(fact: dict[str, Any]) -> dict[str, Any] | None:
            value = number(r"クールタイム\s*0%～-(\d+)%", str(fact.get("effect") or ""))
            return value_row(fact, f"クールタイム 0%～-{display_number(value)}%", "percent_range", value_min=0, value_max=value, label="(2)") if value is not None else None
        return [
            component(row, "random_previous_station_access_1", "random_previous_station_access", condition_value("アクセス済み同属性駅へランダムアクセス", "(1)"), target_scope=["front_car"], condition_raw="先頭車両をアクセス済みの同属性駅へランダムアクセス", label="(1)", role="default_effect", target_filters={"same_attribute_station": True}, trigger_conditions={"access_direction": "active", "event_hint": "remote_access"}),
            component(row, "cooldown_reduction_2", "cooldown_reduction", reduction, target_scope=["own_skill_effects"], condition_raw="(1)でリンク成功時、札幌駅に近いほど自身のクールタイム短縮", label="(2)", role="additional_effect", target_filters={"excluded_skill": "うらら", "distance_reference_station": "札幌駅"}, trigger_conditions={"requires_link_success": True}, scaling_conditions={"basis": "distance_to_sapporo_km", "distance_min_km": 0, "distance_max_km": 1500}, modeling_tags=["not_cooldown_probability_tool"]),
        ]

    if denko_id == "ekico:004":
        def match_bonus(fact: dict[str, Any]) -> dict[str, Any] | None:
            value = number(r"マッチボーナス\s*0～\+(\d+)%", str(fact.get("effect") or ""))
            return value_row(fact, f"マッチボーナス 0～+{display_number(value)}%", "percent_range", value_min=0, value_max=value) if value is not None else None
        return [component(row, "match_bonus", "match_bonus", match_bonus, target_scope=["accessed_denko"], condition_raw=trigger, target_filters={"same_attribute_links": True, "minimum_link_minutes": 15}, trigger_conditions={"access_direction": "passive", "event_hint": "reboot"}, scaling_conditions={"basis": "qualifying_linked_station_count", "count_min": 0, "count_max": 3})]

    if denko_id == "iks:000":
        def debuff(stat: str) -> ValueBuilder:
            def build(fact: dict[str, Any]) -> dict[str, Any] | None:
                effect = str(fact.get("effect") or "")
                base_value = number(rf"{stat}\s*(-\d+)%", effect)
                normal = number(r"\(1\)効果量\s*(\d+(?:\.\d+)?)倍", effect)
                original_extra = number(r"\(2\)効果量\s*(\d+(?:\.\d+)?)倍", effect)
                if None in {base_value, normal, original_extra}:
                    return None
                low = -abs(base_value) * normal
                high = -abs(base_value) * original_extra
                return value_row(fact, f"{stat} {display_number(base_value)}% × 1.02系/Original・Extra倍率", "percent_branch", value_numeric=base_value, value_min=low, value_max=high)
            return build
        filters = {"branch_by_opponent_pool": {"other": "normal_multiplier", "original_extra": "enhanced_multiplier"}}
        scaling = {"basis": "opponent_pool_effect_multiplier"}
        both = {"access_direction": "both", "event_hint": "access_or_accessed"}
        return [
            component(row, "atk_debuff", "atk_debuff", debuff("ATK"), target_scope=["opponent_denko"], condition_raw=trigger, target_filters=filters, trigger_conditions=both, scaling_conditions=scaling),
            component(row, "def_debuff", "def_debuff", debuff("DEF"), target_scope=["opponent_denko"], condition_raw=trigger, target_filters=filters, trigger_conditions=both, scaling_conditions=scaling),
        ]

    if denko_id in {"iks:001", "iks:002", "iks:003"}:
        specs = {
            "iks:001": ("skill_disable", "相手編成内各でんこのスキルを無効化", ["opponent_team"], "both", "all_skill_effects"),
            "iks:002": ("skill_effect_nullification", "被アクセス時、相手を対象としたATK変動スキル効果量を0にする", ["opponent_denko"], "passive", "atk_changing_effects"),
            "iks:003": ("skill_effect_nullification", "アクセス時、相手を対象としたDEF変動スキル効果量を0にする", ["opponent_denko"], "active", "def_changing_effects"),
        }
        kind, condition, scope, direction, disabled_kind = specs[denko_id]
        shared_filters = {
            "disabled_skill_kind": disabled_kind,
            "excluded_when_footbar": denko_id == "iks:001",
        }
        trigger_conditions = {
            "access_direction": direction,
            "event_hint": "access_or_accessed" if direction == "both" else "accessed" if direction == "passive" else "access",
        }
        return [
            component(
                row,
                f"{kind}_non_original_extra",
                kind,
                condition_value(condition, "(1)"),
                target_scope=scope,
                condition_raw=condition,
                target_filters={**shared_filters, "opponent_pool_excludes": ["original", "extra"]},
                trigger_conditions=trigger_conditions,
            ),
            component(
                row,
                f"{kind}_original_extra",
                kind,
                condition_value(condition, "(2)"),
                target_scope=scope,
                condition_raw=condition,
                target_filters={**shared_filters, "opponent_pool_in": ["original", "extra"]},
                trigger_conditions=trigger_conditions,
            ),
        ]

    if denko_id == "iks:004":
        def threshold(label: str) -> ValueBuilder:
            def build(fact: dict[str, Any]) -> dict[str, Any] | None:
                value = number(rf"\({label}\)被ダメージ(\d+)以下無効化", str(fact.get("effect") or ""))
                return value_row(fact, f"被ダメージ{display_number(value)}以下を無効化", "flat_damage_threshold", value_numeric=value, label=f"({label})") if value is not None else None
            return build
        return [
            component(row, "def_buff_1", "def_buff", labeled_numeric(r"\(1\)DEF\s*([+-]\d+)%", "DEF", "percent", "(1)"), target_scope=["self"], condition_raw="自身のDEF増加", label="(1)", role="default_effect"),
            component(row, "damage_nullification_2", "damage_nullification", threshold("2"), target_scope=["self"], condition_raw="相手がOriginal・Extra以外の場合、被ダメージが閾値以下なら無効化", label="(2)", role="additional_effect", target_filters={"opponent_pool_excludes": ["original", "extra"]}, trigger_conditions={"access_direction": "passive", "event_hint": "accessed"}),
            component(row, "damage_nullification_3", "damage_nullification", threshold("3"), target_scope=["self"], condition_raw="相手がOriginal・Extraの場合、被ダメージが閾値以下なら無効化", label="(3)", role="additional_effect", target_filters={"opponent_pool_in": ["original", "extra"]}, trigger_conditions={"access_direction": "passive", "event_hint": "accessed"}),
        ]

    if denko_id == "iks:005":
        def hp_threshold(label: str) -> ValueBuilder:
            def build(fact: dict[str, Any]) -> dict[str, Any] | None:
                value = number(rf"\({label}\)相手HPが(\d+)%以下", str(fact.get("effect") or ""))
                return value_row(fact, f"相手HP {display_number(value)}%以下でリブート", "opponent_hp_percent_threshold", value_numeric=value, label=f"({label})") if value is not None else None
            return build
        active = {"access_direction": "active", "event_hint": "link_failure"}
        return [
            component(row, "reboot_1", "reboot", hp_threshold("1"), target_scope=["opponent_denko"], condition_raw="自身のアクセスでリンク失敗しそうな時、相手HPが閾値以下ならリブート", label="(1)", role="default_effect", target_filters={"opponent_pool_excludes": ["original", "extra"]}, trigger_conditions=active),
            component(row, "reboot_2", "reboot", hp_threshold("2"), target_scope=["opponent_denko"], condition_raw="相手がOriginal・ExtraでHPが閾値以下ならリブート", label="(2)", role="additional_effect", target_filters={"opponent_pool_in": ["original", "extra"]}, trigger_conditions=active),
        ]

    if denko_id == "iks:006":
        def ap(label: str) -> ValueBuilder:
            def build(fact: dict[str, Any]) -> dict[str, Any] | None:
                value = number(rf"\({label}\)\s*AP\s*\+(\d+)", str(fact.get("effect") or ""))
                if value is None:
                    return None
                out = value_row(fact, f"AP +{display_number(value)}", "flat_ap", value_numeric=value, label=f"({label})")
                out["probability"] = {"発動率": "100%"}
                return out
            return build
        active = {"access_direction": "active", "event_hint": "access"}
        return [
            component(row, "ap_buff_1", "ap_buff", ap("1"), target_scope=["self"], condition_raw="自身のアクセス時にAP増加", label="(1)", role="default_effect", trigger_conditions=active),
            component(row, "ap_buff_2", "ap_buff", ap("2"), target_scope=["self"], condition_raw="相手がOriginal・Extraの場合にAP追加増加", label="(2)", role="additional_effect", target_filters={"opponent_pool_in": ["original", "extra"]}, trigger_conditions=active),
            component(row, "reboot_self_3", "reboot", condition_value("自身がリブート", "(3)"), target_scope=["self"], condition_raw="相手をリブートしてリンクした場合、20%で自身がリブート", label="(3)", role="self_debuff", trigger_conditions={"access_direction": "active", "event_hint": "link_success_after_reboot"}, modeling_tags=["not_standalone_report_candidate"], self_debuff_note="相手をリブートしてリンクすると20%で自身もリブート"),
        ]

    raise KeyError(f"missing reviewed special semantics: {denko_id}")


def backfill_row(row: dict[str, Any]) -> None:
    components = components_for(row)
    row["skill_components"] = sorted(components, key=base.component_sort_key)
    row["normalized_skill"] = {
        "effect_kind": sorted({component["effect_kind"] for component in components}),
        "target_scope": sorted({scope for component in components for scope in component.get("target_scope") or []}),
        "trigger": {},
        "activation_mode": row.get("activation_type"),
        "confidence": "high",
        "review_reasons": [],
        "available_denko_levels": sorted({level for component in components for level in component.get("values_by_denko_level") or {}}, key=int),
    }
    row["summary_zh"] = base.build_summary_zh(components, row["normalized_skill"], row.get("lv50"), row.get("values_by_denko_level"))
    row["note_zh"] = "特殊系列详情页已完成语义复查并结构化。"
    meta = row.setdefault("record_meta", {})
    meta["confidence"] = "high"
    meta["needs_review"] = False
    meta["review_reasons"] = []
    meta["parser_version"] = base.PARSER_VERSION
    meta.setdefault("postprocess", {})["special_pool_semantics"] = {
        "backfill_version": BACKFILL_VERSION,
        "component_count": len(components),
    }


def run_backfill() -> list[dict[str, Any]]:
    results = []
    for path in sorted(RECORD_DIR.glob("*_skill_facts.jsonl")):
        pool = path.name.split("_", 1)[0]
        if pool not in POOLS:
            continue
        rows = read_jsonl(path)
        for row in rows:
            backfill_row(row)
        write_jsonl(path, rows)
        results.append({"path": str(path.relative_to(ROOT)), "rows": len(rows)})
    return results


def main() -> None:
    results = run_backfill()
    print(json.dumps({"backfill_version": BACKFILL_VERSION, "results": results}, ensure_ascii=False))


if __name__ == "__main__":
    main()
