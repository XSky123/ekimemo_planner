from __future__ import annotations

import argparse
import html
import json
import random
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urldefrag, urljoin
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

import parse as base


URLS = {
    "original": "https://newekimemo.wiki.fc2.com/wiki/%E5%88%9D%E5%BF%83%E8%80%85%E5%90%91%E3%81%91%E3%82%AA%E3%83%AA%E3%82%B8%E3%83%8A%E3%83%AB%E3%81%A7%E3%82%93%E3%81%93%E3%82%AA%E3%82%B9%E3%82%B9%E3%83%A1%E5%BA%A6",
    "extra": "https://newekimemo.wiki.fc2.com/wiki/%E5%88%9D%E5%BF%83%E8%80%85%E5%90%91%E3%81%91%E3%82%A8%E3%82%AF%E3%82%B9%E3%83%88%E3%83%A9%E3%81%A7%E3%82%93%E3%81%93%E3%82%AA%E3%82%B9%E3%82%B9%E3%83%A1%E5%BA%A6",
}
OUT_JSON = base.ROOT / "data" / "agent_runs" / "recommendation_prior_full_audit.json"
OUT_HTML = base.ROOT / "data" / "reports" / "recommendation_prior_full_audit_zh.html"
ATTRIBUTES = ("heat", "cool", "eco", "flat")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def fetch_html(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 recommendation-prior-audit/1.0"})
    with urlopen(req, timeout=30) as response:
        return response.read()


def int_attr(node: Any, key: str) -> int:
    value = node.get(key)
    if not value:
        return 1
    try:
        return int(value)
    except ValueError:
        return 1


def matrix_rows(table: Any) -> list[tuple[list[str], list[tuple[str, str]], dict[str, Any]]]:
    spans: dict[int, tuple[int, str, list[tuple[str, str]]]] = {}
    rows: list[tuple[list[str], list[tuple[str, str]], dict[str, Any]]] = []
    for row_index, tr in enumerate(table.find_all("tr")):
        row: list[str] = []
        links: list[tuple[str, str]] = []
        inherited_columns = 0
        col = 0
        for cell in tr.find_all(["th", "td"], recursive=False):
            while col in spans:
                remaining, text, cell_links = spans[col]
                row.append(text)
                links.extend(cell_links)
                inherited_columns += 1
                if remaining <= 1:
                    del spans[col]
                else:
                    spans[col] = (remaining - 1, text, cell_links)
                col += 1
            text = cell.get_text(" ", strip=True)
            cell_links = [
                (a.get_text(" ", strip=True), href)
                for a in cell.find_all("a")
                if (href := a.get("href"))
            ]
            rowspan = int_attr(cell, "rowspan")
            colspan = int_attr(cell, "colspan")
            for _ in range(colspan):
                row.append(text)
                links.extend(cell_links)
                if rowspan > 1:
                    spans[col] = (rowspan - 1, text, cell_links)
                col += 1
        while col in spans:
            remaining, text, cell_links = spans[col]
            row.append(text)
            links.extend(cell_links)
            inherited_columns += 1
            if remaining <= 1:
                del spans[col]
            else:
                spans[col] = (remaining - 1, text, cell_links)
            col += 1
        rows.append((row, links, {"row_index": row_index, "inherited_columns": inherited_columns}))
    return rows


def recommendation_rows(pool: str, url: str, url_to_id: dict[str, str]) -> list[dict[str, Any]]:
    soup = BeautifulSoup(fetch_html(url), "html.parser")
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for table_index, table in enumerate(soup.find_all("table")):
        for cells, links, meta in matrix_rows(table):
            if len(cells) < 5:
                continue
            matched_id = None
            matched_short_name = None
            matched_url = None
            for text, href in links:
                absolute = urldefrag(urljoin(url, href))[0]
                denko_id = url_to_id.get(absolute)
                if denko_id and denko_id.startswith(f"{pool}:"):
                    matched_id = denko_id
                    matched_short_name = text
                    matched_url = absolute
                    break
            if not matched_id:
                continue
            row_text = " / ".join(cells)
            key = (matched_id, row_text)
            if key in seen:
                continue
            seen.add(key)
            out.append(
                {
                    "pool": pool,
                    "denko_id": matched_id,
                    "short_name": matched_short_name,
                    "detail_url": matched_url,
                    "row_text": row_text,
                    "cells": cells,
                    "table_index": table_index,
                    **meta,
                }
            )
    return out


def compact(value: Any, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def skill_blob(row: dict[str, Any]) -> str:
    pieces: list[str] = []
    for key in ["skill_name", "effect_summary", "trigger_condition", "activation_type", "skill_remarks", "summary_zh", "note_zh"]:
        value = row.get(key)
        if isinstance(value, str):
            pieces.append(value)
        elif isinstance(value, list):
            pieces.extend(str(item) for item in value)
    pieces.extend(json.dumps(component, ensure_ascii=False) for component in row.get("skill_components") or [])
    return " ".join(pieces)


def component_kinds(row: dict[str, Any]) -> set[str]:
    return {str(component.get("effect_kind")) for component in row.get("skill_components") or [] if component.get("effect_kind")}


def all_target_filters(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [component.get("target_filters") or {} for component in row.get("skill_components") or []]


def all_triggers(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [component.get("trigger_conditions") or {} for component in row.get("skill_components") or []]


def has_own_team_all_attribute(row: dict[str, Any], attr: str) -> bool:
    blob = skill_blob(row)
    if f"{attr}属性のみ" in blob or f"すべて{attr}属性" in blob or f"全て{attr}属性" in blob:
        return True
    return any(filters.get("own_team_all_attribute") == attr for filters in all_target_filters(row))


def has_opponent_attribute(row: dict[str, Any], attr: str) -> bool:
    return any(
        filters.get("opponent_attribute") == attr
        or (filters.get("opponent_team_attribute_count") or {}).get("attribute") == attr
        or (filters.get("opponent_team_attribute_min_count") or {}).get("attribute") == attr
        for filters in all_target_filters(row)
    )


def has_access_direction(row: dict[str, Any], direction: str) -> bool:
    return any(
        trigger.get("access_direction") == direction or direction in (trigger.get("access_directions") or [])
        for trigger in all_triggers(row)
    )


def row_has_any(row: dict[str, Any], needles: list[str]) -> bool:
    blob = skill_blob(row)
    return any(needle in blob for needle in needles)


CLAIMS = [
    {
        "id": "atk_buff",
        "patterns": ["ATK増加", "ATK大幅増加", "攻撃力増加"],
        "kinds": {"atk_buff"},
        "severity": "warn",
        "reason_zh": "推荐语提到 ATK 增加，但 DB 中未找到 ATK buff",
    },
    {
        "id": "atk_debuff",
        "patterns": ["ATK減少", "ATKを減少"],
        "kinds": {"atk_debuff"},
        "severity": "warn",
        "reason_zh": "推荐语提到 ATK 减少，但 DB 中未找到 ATK debuff",
    },
    {
        "id": "def_buff",
        "patterns": ["DEF増加", "DEFが増加"],
        "kinds": {"def_buff"},
        "severity": "warn",
        "reason_zh": "推荐语提到 DEF 增加/防御，但 DB 中未找到 DEF buff",
    },
    {
        "id": "def_debuff",
        "patterns": ["DEF減少", "DEFを減少"],
        "kinds": {"def_debuff"},
        "severity": "warn",
        "reason_zh": "推荐语提到 DEF 减少，但 DB 中未找到 DEF debuff",
    },
    {
        "id": "damage_reduction",
        "patterns": ["ダメージを軽減", "ダメージ軽減", "被ダメージ", "受けるダメージ"],
        "kinds": {"damage_reduction", "damage_cap", "damage_nullification", "damage_substitution"},
        "severity": "warn",
        "reason_zh": "推荐语提到伤害轻减/被伤害，但 DB 中未找到对应防御类效果",
    },
    {
        "id": "fixed_damage",
        "patterns": ["固定ダメージを与える", "固定ダメージ付与", "軽減されないダメージを与える"],
        "kinds": {"fixed_damage", "additional_fixed_damage"},
        "severity": "warn",
        "reason_zh": "推荐语提到固定/不可轻减伤害，但 DB 中未找到固定伤害类效果",
    },
    {
        "id": "hp_recovery",
        "patterns": ["HP回復", "回復するスキル", "HPを回復"],
        "kinds": {"hp_recovery"},
        "severity": "warn",
        "reason_zh": "推荐语提到 HP 回复，但 DB 中未找到 HP recovery",
    },
    {
        "id": "experience",
        "patterns": ["経験値"],
        "kinds": {"exp_gain", "exp_distribution", "effect_multiplier"},
        "severity": "warn",
        "reason_zh": "推荐语提到经验值，但 DB 中未找到经验/经验倍率类效果",
    },
    {
        "id": "score",
        "patterns": ["スコア"],
        "kinds": {"score_gain", "additional_score_gain", "score_random_modifier"},
        "severity": "warn",
        "reason_zh": "推荐语提到分数，但 DB 中未找到 score 类效果",
    },
    {
        "id": "activation_probability",
        "patterns": ["スキル発動率", "発動率を増加"],
        "kinds": {"activation_probability_boost"},
        "severity": "warn",
        "reason_zh": "推荐语提到技能发动率增加，但 DB 中未找到 activation probability boost",
    },
    {
        "id": "cooldown",
        "patterns": ["クールタイム", "CT"],
        "kinds": {"cooldown_reset", "cooldown_reduction"},
        "fallback_needles": ["cooldown", "クールタイム"],
        "severity": "info",
        "reason_zh": "推荐语提到 CD/冷却，但 DB 中未找到冷却类效果或冷却字段",
    },
    {
        "id": "skill_disable",
        "patterns": ["スキル無効", "スキルを無効化", "フットバース無効化"],
        "kinds": {"skill_disable", "skill_nullification", "damage_nullification"},
        "severity": "warn",
        "reason_zh": "推荐语提到无效化，但 DB 中未找到无效化类效果",
    },
    {
        "id": "link_bonus",
        "patterns": ["リンクボーナス"],
        "kinds": {"link_bonus"},
        "severity": "warn",
        "reason_zh": "推荐语提到 link bonus，但 DB 中未找到 link_bonus",
    },
    {
        "id": "new_station_bonus",
        "patterns": ["今日の新駅にアクセス時のボーナス", "今日の新駅ボーナス"],
        "kinds": {"today_new_station_bonus"},
        "severity": "warn",
        "reason_zh": "推荐语提到今日の新駅 bonus，但 DB 中未找到对应效果",
    },
    {
        "id": "film_effect",
        "patterns": ["フィルム"],
        "kinds": {"film_effect_multiplier", "film_series_effect_boost"},
        "severity": "warn",
        "reason_zh": "推荐语提到 film 效果，但 DB 中未找到 film effect multiplier",
    },
    {
        "id": "accessory_effect",
        "patterns": ["アクセサリー"],
        "kinds": {"effect_multiplier"},
        "severity": "warn",
        "reason_zh": "推荐语提到 accessory 效果，但 DB 中未找到 effect multiplier",
    },
    {
        "id": "link_retention",
        "patterns": ["リンクを保持して復活", "リンク継続", "リンクを手放さず"],
        "kinds": {"link_retention", "link_continue"},
        "severity": "warn",
        "reason_zh": "推荐语提到 link 保持/継続，但 DB 中未找到 link_retention",
    },
    {
        "id": "link_transfer",
        "patterns": ["譲渡", "受け渡す駅"],
        "kinds": {"station_link_transfer"},
        "severity": "warn",
        "reason_zh": "推荐语提到 link/駅 譲渡，但 DB 中未找到 station_link_transfer",
    },
    {
        "id": "counter",
        "patterns": ["カウンター"],
        "kinds": {"counter", "reboot"},
        "severity": "warn",
        "reason_zh": "推荐语提到 counter，但 DB 中未找到 counter/reboot 类效果",
    },
    {
        "id": "ap_debuff",
        "patterns": ["AP減少"],
        "kinds": {"ap_debuff"},
        "severity": "warn",
        "reason_zh": "推荐语提到 AP 减少，但 DB 中未找到 ap_debuff",
    },
]


def recommendation_mentions_claim(text: str, claim: dict[str, Any]) -> bool:
    if claim["id"] == "atk_buff" and any(
        phrase in text
        for phrase in [
            "ATK増加より",
            "ATK増加のでんこと組み合わせ",
            "ATKを大きく増加させるでんこの組み合わせ",
            "ATK増加・DEF増加でんこを組み合わせ",
        ]
    ):
        return False
    if claim["id"] == "def_buff" and any(
        phrase in text
        for phrase in [
            "DEF増加でんこと組み合わせ",
            "DEF増加との違い",
            "単純なDEF増加より",
            "DEFを増加させられる他のでんこ",
            "DEF増加ほどではない",
            "DEF増加でんこを組み合わせ",
            "ATK増加・DEF増加でんこを組み合わせ",
        ]
    ):
        return False
    if claim["id"] == "damage_reduction" and (
        ("AP減少" in text and "被ダメージを減らしやすい" in text)
        or "防御スキルの重ね掛け" in text
    ):
        return False
    if claim["id"] == "experience" and "必要な経験値" in text:
        return False
    if claim["id"] == "experience" and any(phrase in text for phrase in ["経験値獲得狙いの相手", "相手に経験値を与えてしまう"]):
        return False
    if claim["id"] == "score" and any(phrase in text for phrase in ["スコア稼ぎに愛用", "スコアの獲得に置かれている"]):
        return "スコア変動" in text
    if claim["id"] == "score" and "獲得スコアが高い相手" in text:
        return False
    if claim["id"] == "counter" and "カウンターと併用" in text:
        return False
    if claim["id"] == "link_bonus" and "リンクボーナスが0" in text:
        return False
    if claim["id"] == "skill_disable" and "無効化されない" in text:
        return False
    return any(pattern in text for pattern in claim["patterns"])


def row_satisfies_claim(row: dict[str, Any], claim: dict[str, Any]) -> bool:
    kinds = component_kinds(row)
    if kinds & set(claim.get("kinds") or []):
        return True
    if claim["id"] in {"experience", "score"} and "today_new_station_bonus" in kinds:
        return True
    if claim["id"] == "atk_buff" and "effect_multiplier" in kinds and "ATK増加" in skill_blob(row):
        return True
    if claim["id"] == "def_buff" and "effect_multiplier" in kinds and "DEF増加" in skill_blob(row):
        return True
    if claim["id"] == "score" and "effect_multiplier" in kinds and "スコア" in skill_blob(row):
        return True
    fallback_needles = claim.get("fallback_needles") or []
    return bool(fallback_needles and row_has_any(row, fallback_needles))


def expected_attributes(text: str) -> list[str]:
    out: list[str] = []
    for attr in ATTRIBUTES:
        patterns = [
            f"{attr} 統一編成",
            f"{attr}統一編成",
            f"{attr}属性のみ",
            f"すべて{attr}属性",
            f"全て{attr}属性",
        ]
        if any(pattern in text for pattern in patterns):
            out.append(attr)
    return out


def opponent_attributes(text: str) -> list[str]:
    out: list[str] = []
    for attr in ATTRIBUTES:
        patterns = [
            f"相手が{attr}",
            f"相手が {attr}",
            f"相手の{attr}",
            f"相手の {attr}",
            f"相手編成が{attr}",
            f"対{attr}",
        ]
        if any(pattern in text for pattern in patterns):
            out.append(attr)
    return out


def audit_row(candidate: dict[str, Any], skill_row: dict[str, Any]) -> dict[str, Any]:
    text = candidate["row_text"]
    findings: list[dict[str, Any]] = []
    expected_claims: list[str] = []
    matched_claims: list[str] = []
    kinds = sorted(component_kinds(skill_row))

    if not skill_row.get("skill_components"):
        findings.append(
            {
                "severity": "blocker",
                "code": "skill_components_empty",
                "reason_zh": "DB 中 skill_components 为空",
            }
        )

    grouped_recommendation = "それぞれ" in text and "/" in text
    for claim in CLAIMS:
        if not recommendation_mentions_claim(text, claim):
            continue
        expected_claims.append(claim["id"])
        if row_satisfies_claim(skill_row, claim):
            matched_claims.append(claim["id"])
            continue
        if grouped_recommendation:
            continue
        if not recommendation_mentions_claim(skill_blob(skill_row), claim):
            findings.append(
                {
                    "severity": "info",
                    "code": f"prior_detail_conflict:{claim['id']}",
                    "reason_zh": f"推荐页 prior 提到 {claim['id']}，但详情页事实中未确认；不覆盖 DB",
                }
            )
            continue
        severity = "info" if grouped_recommendation else claim["severity"]
        findings.append(
            {
                "severity": severity,
                "code": f"claim_missing:{claim['id']}",
                "reason_zh": claim["reason_zh"] + ("；推荐语疑似为合并说明，降级为 info" if grouped_recommendation else ""),
            }
        )

    for attr in expected_attributes(text):
        expected_claims.append(f"own_team_all_attribute:{attr}")
        if has_own_team_all_attribute(skill_row, attr):
            matched_claims.append(f"own_team_all_attribute:{attr}")
        else:
            findings.append(
                {
                    "severity": "warn",
                    "code": f"own_team_all_attribute_missing:{attr}",
                    "reason_zh": f"推荐语提到 {attr} 统/仅属性编成，但 DB 中未找到 own_team_all_attribute={attr}",
                }
            )

    for attr in opponent_attributes(text):
        if grouped_recommendation:
            continue
        expected_claims.append(f"opponent_attribute:{attr}")
        if has_opponent_attribute(skill_row, attr):
            matched_claims.append(f"opponent_attribute:{attr}")
        else:
            findings.append(
                {
                    "severity": "warn",
                    "code": f"opponent_attribute_missing:{attr}",
                    "reason_zh": f"推荐语提到对手 {attr} 属性，但 DB 中未找到 opponent_attribute={attr}",
                }
            )

    passive_trigger_text = (
        "被アクセス時に" in text
        or "アクセスされたとき" in text
        or "アクセスされた時" in text
        or "アクセスされると" in text
    )
    passive_context_only = "相手でんこの被アクセス時効果" in text or "被アクセスの多い" in text
    if passive_trigger_text and not passive_context_only and not grouped_recommendation:
        expected_claims.append("access_direction:passive")
        if has_access_direction(skill_row, "passive"):
            matched_claims.append("access_direction:passive")
        else:
            findings.append(
                {
                    "severity": "warn",
                    "code": "passive_access_missing",
                    "reason_zh": "推荐语提到被访问触发，但 DB 中未找到 passive access_direction",
                }
            )

    if re.search(r"アクセス時|アクセスした時|アクセスしたとき", text) and "被アクセス" not in text and not grouped_recommendation:
        expected_claims.append("access_direction:active")
        if has_access_direction(skill_row, "active"):
            matched_claims.append("access_direction:active")
        else:
            findings.append(
                {
                    "severity": "info",
                    "code": "active_access_missing",
                    "reason_zh": "推荐语提到访问时触发，但 DB 中未找到 active access_direction",
                }
            )

    severity_rank = {"blocker": 3, "warn": 2, "info": 1}
    max_severity = "ok"
    if findings:
        max_severity = max(findings, key=lambda item: severity_rank[item["severity"]])["severity"]
    return {
        **candidate,
        "name": skill_row.get("name"),
        "skill_name": skill_row.get("skill_name"),
        "component_kinds": kinds,
        "expected_claims": expected_claims,
        "matched_claims": matched_claims,
        "findings": findings,
        "max_severity": max_severity,
        "summary_zh": skill_row.get("summary_zh"),
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def write_html(path: Path, audit: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = audit["rows"]
    issue_rows = [row for row in rows if row["findings"]]
    issue_rows.sort(key=lambda row: {"blocker": 0, "warn": 1, "info": 2, "ok": 3}[row["max_severity"]])
    sample_ok = [row for row in rows if not row["findings"]]
    random.Random(20260616).shuffle(sample_ok)
    sample_ok = sample_ok[:20]
    esc = html.escape
    parts = [
        "<!doctype html><html><head><meta charset=\"utf-8\">",
        "<title>推荐语全量审计</title>",
        "<style>",
        "body{font-family:system-ui,'Microsoft YaHei',sans-serif;margin:24px;color:#202124;background:#fafafa}",
        "h1{font-size:24px} h2{font-size:18px;margin-top:28px}",
        "table{border-collapse:collapse;width:100%;background:white;margin:12px 0}",
        "th,td{border:1px solid #d0d7de;padding:6px 8px;vertical-align:top;font-size:13px}",
        "th{background:#f1f3f4}.blocker{background:#ffe7e7}.warn{background:#fff4d6}.info{background:#eef5ff}.ok{background:#eef9ee}",
        "code{font-family:ui-monospace,Consolas,monospace;font-size:12px}",
        "</style></head><body>",
        "<h1>推荐语全量审计</h1>",
        f"<p>生成时间：{esc(audit['generated_at'])}</p>",
        "<table><tbody>",
        f"<tr><th>候选推荐行</th><td>{audit['candidate_count']}</td></tr>",
        f"<tr><th>有发现的行</th><td>{audit['issue_row_count']}</td></tr>",
        f"<tr><th>发现数</th><td>{audit['finding_count']}</td></tr>",
        f"<tr><th>严重度统计</th><td><code>{esc(json.dumps(audit['severity_counts'], ensure_ascii=False))}</code></td></tr>",
        "</tbody></table>",
        "<h2>可疑项目</h2>",
    ]
    if issue_rows:
        parts.append("<table><thead><tr><th>severity</th><th>denko</th><th>推荐语</th><th>DB 技能摘要</th><th>发现</th><th>kinds</th></tr></thead><tbody>")
        for row in issue_rows:
            findings = "<br>".join(
                f"<b>{esc(item['severity'])}</b> <code>{esc(item['code'])}</code>: {esc(item['reason_zh'])}"
                for item in row["findings"]
            )
            parts.append(
                f"<tr class=\"{esc(row['max_severity'])}\">"
                f"<td>{esc(row['max_severity'])}</td>"
                f"<td><code>{esc(row['denko_id'])}</code><br>{esc(row.get('name') or '')}<br>{esc(row.get('skill_name') or '')}</td>"
                f"<td>{esc(compact(row['row_text'], 360))}</td>"
                f"<td>{esc(compact(row.get('summary_zh'), 260))}</td>"
                f"<td>{findings}</td>"
                f"<td><code>{esc(', '.join(row.get('component_kinds') or []))}</code></td>"
                "</tr>"
            )
        parts.append("</tbody></table>")
    else:
        parts.append("<p>没有发现 blocker/warn/info。</p>")
    parts.append("<h2>随机 OK 样本</h2>")
    parts.append("<table><thead><tr><th>denko</th><th>推荐语</th><th>DB kinds</th></tr></thead><tbody>")
    for row in sample_ok:
        parts.append(
            f"<tr class=\"ok\"><td><code>{esc(row['denko_id'])}</code><br>{esc(row.get('name') or '')}</td>"
            f"<td>{esc(compact(row['row_text'], 260))}</td>"
            f"<td><code>{esc(', '.join(row.get('component_kinds') or []))}</code></td></tr>"
        )
    parts.extend(["</tbody></table>", "</body></html>"])
    path.write_text("\n".join(parts), encoding="utf-8")


def build_audit() -> dict[str, Any]:
    skill_rows = read_jsonl(base.ROOT / "data" / "step1_db" / "skill_facts.jsonl")
    skill_by_id = {row["denko_id"]: row for row in skill_rows}
    url_to_id = {
        urldefrag(row.get("detail_url") or "")[0]: row["denko_id"]
        for row in skill_rows
        if row.get("detail_url")
    }
    candidates: list[dict[str, Any]] = []
    for pool, url in URLS.items():
        candidates.extend(recommendation_rows(pool, url, url_to_id))
    rows = [audit_row(candidate, skill_by_id[candidate["denko_id"]]) for candidate in candidates if candidate["denko_id"] in skill_by_id]
    findings = [finding for row in rows for finding in row["findings"]]
    severity_counts = Counter(finding["severity"] for finding in findings)
    return {
        "generated_at": datetime.now(base.JST).isoformat(),
        "source_urls": URLS,
        "candidate_count": len(candidates),
        "audited_count": len(rows),
        "issue_row_count": sum(1 for row in rows if row["findings"]),
        "finding_count": len(findings),
        "severity_counts": dict(sorted(severity_counts.items())),
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=OUT_JSON)
    parser.add_argument("--html", type=Path, default=OUT_HTML)
    args = parser.parse_args()
    audit = build_audit()
    write_json(args.json, audit)
    write_html(args.html, audit)
    print(
        json.dumps(
            {
                "candidate_count": audit["candidate_count"],
                "audited_count": audit["audited_count"],
                "issue_row_count": audit["issue_row_count"],
                "finding_count": audit["finding_count"],
                "severity_counts": audit["severity_counts"],
                "json": str(args.json),
                "html": str(args.html),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
