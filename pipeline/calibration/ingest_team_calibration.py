from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DENKO = ROOT / "data/step1_db/denko_facts.jsonl"
OUT = ROOT / "data/observed_cases/team_calibration.json"
TEAM_ENTRY_SUFFIX = "data/derived_current/team_templates_20260711.json"
OPPONENT_ENTRY_SUFFIX = "source_snapshot/opponent_database.json"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def clean_member(value: str) -> str:
    value = re.sub(r"Lv\.?\s*\d+.*$", "", value).strip()
    value = re.sub(r"（(?:EX\s*)?No\.\s*\d+）", "", value).strip()
    return value


def resolver() -> tuple[dict[str, str], dict[str, list[str]]]:
    exact: dict[str, str] = {}
    suffixes: dict[str, list[str]] = defaultdict(list)
    for row in read_jsonl(DENKO):
        identity = row.get("identity") or {}
        denko_id = str(identity.get("denko_id") or row.get("denko_id"))
        for value in {identity.get("name"), identity.get("full_name"), identity.get("wiki_page_title")}:
            if not value:
                continue
            name = str(value)
            exact[name] = denko_id
            for length in range(2, min(6, len(name)) + 1):
                suffixes[name[-length:]].append(denko_id)
    return exact, suffixes


def resolve_member(value: str, exact: dict[str, str], suffixes: dict[str, list[str]]) -> str | None:
    ex = re.search(r"EX\s*No\.\s*(\d+)", value)
    if ex:
        return f"extra:{int(ex.group(1)):03d}"
    original = re.search(r"(?<!EX\s)No\.\s*(\d+)", value)
    if original:
        return f"original:{int(original.group(1)):03d}"
    name = clean_member(value)
    if name in exact:
        return exact[name]
    candidates = sorted(set(suffixes.get(name, [])))
    return candidates[0] if len(candidates) == 1 else None


def template_context(key: str) -> str:
    if key in {"new_station_monthly_scoring"}:
        return "score_gain"
    if key in {"normal_exp_running", "cat_punch_spending"}:
        return "exp_gain"
    return "attack_front"


def availability_weight(value: str | None) -> float:
    return {
        "current_available": 1.0,
        "current_with_placeholder_target": 0.9,
        "future_not_owned": 0.45,
        "deprecated_after_nagisa_lv60": 0.25,
    }.get(str(value), 0.7)


def add_team(
    output: list[dict[str, Any]], *, team_id: str, origin: str, members: list[str],
    context: str, weight: float, evidence: dict[str, Any], exact: dict[str, str], suffixes: dict[str, list[str]],
) -> None:
    parsed = []
    for index, member in enumerate(members):
        parsed.append({
            "position": index + 1, "raw": member, "name": clean_member(member),
            "denko_id": resolve_member(member, exact, suffixes),
            "slot": "leader" if index == 0 else "support",
        })
    output.append({
        "team_id": team_id, "origin": origin, "context": context, "quality_weight": weight,
        "members": parsed, "evidence": evidence,
    })


def opponent_teams(database: dict[str, Any], exact: dict[str, str], suffixes: dict[str, list[str]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    players = (database.get("major_local_players") or {})
    for player, payload in players.items():
        classification = str(payload.get("classification") or "")
        weight = 1.25 if "GM" in classification or "SM" in classification or "strong" in classification else 0.8
        if payload.get("forms"):
            for form, item in payload["forms"].items():
                context = "attack_front" if "reno" in form.lower() else "defense_front"
                add_team(result, team_id=f"opponent:{player}:{form}", origin="opponent_database", members=item.get("team") or [], context=context, weight=weight, evidence={"classification": classification, "results": item.get("results") or [], "counter": item.get("counter")}, exact=exact, suffixes=suffixes)
        for index, members in enumerate(payload.get("common_team_examples") or [], 1):
            add_team(result, team_id=f"opponent:{player}:common:{index}", origin="opponent_database", members=members, context="defense_front", weight=weight, evidence={"classification": classification, "results": payload.get("results") or [], "counter": payload.get("counter")}, exact=exact, suffixes=suffixes)
        if payload.get("team"):
            context = "attack_front" if "attacker" in classification.lower() else "defense_front"
            add_team(result, team_id=f"opponent:{player}:team", origin="opponent_database", members=payload["team"], context=context, weight=weight, evidence={"classification": classification, "results": payload.get("results") or [], "counter": payload.get("counter")}, exact=exact, suffixes=suffixes)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    archive_path = args.archive.resolve()
    archive_bytes = archive_path.read_bytes()
    exact, suffixes = resolver()
    with zipfile.ZipFile(archive_path) as archive:
        team_entry = next(name for name in archive.namelist() if name.endswith(TEAM_ENTRY_SUFFIX))
        opponent_entry = next(name for name in archive.namelist() if name.endswith(OPPONENT_ENTRY_SUFFIX))
        team_bytes = archive.read(team_entry)
        opponent_bytes = archive.read(opponent_entry)
    templates = json.loads(team_bytes.decode("utf-8-sig"))
    opponents = json.loads(opponent_bytes.decode("utf-8-sig"))
    teams: list[dict[str, Any]] = []
    for key, payload in templates.items():
        add_team(
            teams, team_id=f"template:{key}", origin="user_template", members=payload.get("team") or [],
            context=template_context(key), weight=availability_weight(payload.get("availability")),
            evidence={"availability": payload.get("availability"), "use_cases": payload.get("use_cases") or [], "notes": payload.get("notes"), "warning": payload.get("warning")},
            exact=exact, suffixes=suffixes,
        )
    teams.extend(opponent_teams(opponents, exact, suffixes))
    usage: dict[str, dict[str, Any]] = {}
    unresolved: list[dict[str, Any]] = []
    for team in teams:
        for member in team["members"]:
            denko_id = member["denko_id"]
            if not denko_id:
                if member["name"] not in {"目标角色", ""}:
                    unresolved.append({"team_id": team["team_id"], "raw": member["raw"]})
                continue
            item = usage.setdefault(denko_id, {"weighted_appearances": 0.0, "weighted_leader_appearances": 0.0, "team_count": 0, "leader_count": 0, "contexts": defaultdict(float), "use_case_signals": defaultdict(float), "team_ids": []})
            item["weighted_appearances"] += team["quality_weight"]
            item["team_count"] += 1
            item["contexts"][team["context"]] += team["quality_weight"]
            signal = team["context"]
            if member["slot"] == "support" and signal == "attack_front":
                signal = "attack_support"
            elif member["slot"] == "support" and signal == "defense_front":
                signal = "defense_support"
            item["use_case_signals"][signal] += team["quality_weight"]
            item["team_ids"].append(team["team_id"])
            if member["slot"] == "leader":
                item["weighted_leader_appearances"] += team["quality_weight"]
                item["leader_count"] += 1
    normalized_usage = {
        key: {
            **value,
            "weighted_appearances": round(value["weighted_appearances"], 3),
            "weighted_leader_appearances": round(value["weighted_leader_appearances"], 3),
            "contexts": {name: round(weight, 3) for name, weight in sorted(value["contexts"].items())},
            "use_case_signals": {name: round(weight, 3) for name, weight in sorted(value["use_case_signals"].items())},
            "team_ids": sorted(value["team_ids"]),
        }
        for key, value in sorted(usage.items())
    }
    result = {
        "artifact": "observed_team_calibration", "version": "observed_team_calibration.v1",
        "source": {
            "archive_name": archive_path.name, "archive_hash": sha256(archive_bytes),
            "entries": [
                {"path": team_entry, "hash": sha256(team_bytes)},
                {"path": opponent_entry, "hash": sha256(opponent_bytes)},
            ],
            "source_authority": "observed_case", "calibration_only": True,
        },
        "counts": {"teams": len(teams), "resolved_denko": len(normalized_usage), "unresolved_members": len(unresolved)},
        "teams": teams, "denko_usage": normalized_usage, "unresolved_members": unresolved,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
