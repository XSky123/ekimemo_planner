from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin


ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data" / "raw_pages"
RECORD_DIR = ROOT / "data" / "records"
INDEX_DIR = ROOT / "data" / "indexes"
REVIEW_DIR = ROOT / "data" / "review_queue"
REPORT_DIR = ROOT / "data" / "reports"
BASE_URL = "https://newekimemo.wiki.fc2.com"
JST = timezone(timedelta(hours=9))
PARSER_VERSION = "sample_first5_html_table_matrix.v1"

LIST_PAGES = {
    "original": "https://newekimemo.wiki.fc2.com/wiki/%E9%A1%94%E7%94%BB%E5%83%8F%E3%83%BB%E3%82%BF%E3%82%A4%E3%83%97%E3%83%BB%E5%B1%9E%E6%80%A7%E3%83%BB%E8%89%B2%E3%83%BB%E3%82%B9%E3%82%AD%E3%83%AB%E5%90%8D%2F%E3%82%AA%E3%83%AA%E3%82%B8%E3%83%8A%E3%83%AB%E3%81%A7%E3%82%93%E3%81%93",
    "extra": "https://newekimemo.wiki.fc2.com/wiki/%E9%A1%94%E7%94%BB%E5%83%8F%E3%83%BB%E3%82%BF%E3%82%A4%E3%83%97%E3%83%BB%E5%B1%9E%E6%80%A7%E3%83%BB%E8%89%B2%E3%83%BB%E3%82%B9%E3%82%AD%E3%83%AB%E5%90%8D%2F%E3%82%A8%E3%82%AF%E3%82%B9%E3%83%88%E3%83%A9%E3%81%A7%E3%82%93%E3%81%93",
}


@dataclass
class Node:
    tag: str
    attrs: dict[str, str] = field(default_factory=dict)
    children: list["Node"] = field(default_factory=list)
    text_parts: list[str] = field(default_factory=list)

    def text(self) -> str:
        parts: list[str] = []
        parts.extend(self.text_parts)
        for child in self.children:
            parts.append(child.text())
        return normalize_text(" ".join(parts))

    def find_all(self, tag: str) -> list["Node"]:
        found: list[Node] = []
        if self.tag == tag:
            found.append(self)
        for child in self.children:
            found.extend(child.find_all(tag))
        return found

    def first_link(self) -> dict[str, str | None]:
        for child in self.find_all("a"):
            href = child.attrs.get("href")
            title = child.attrs.get("title")
            text = child.text()
            if href or text:
                return {"href": href, "title": title, "text": text}
        return {"href": None, "title": None, "text": None}


class TreeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("document")
        self.stack = [self.root]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        node = Node(tag.lower(), {k.lower(): (v or "") for k, v in attrs})
        self.stack[-1].children.append(node)
        if tag.lower() not in {"br", "img", "meta", "link", "input"}:
            self.stack.append(node)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data: str) -> None:
        if data:
            self.stack[-1].text_parts.append(data)


def normalize_text(value: str) -> str:
    value = html.unescape(value).replace("\xa0", " ")
    return re.sub(r"\s+", " ", value).strip()


def fetch(url: str, out_path: Path) -> str:
    if out_path.exists():
        return out_path.read_text(encoding="utf-8", errors="replace")
    req = urllib.request.Request(url, headers={"User-Agent": "ekimemo-planner-sample/0.1"})
    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read()
    text = body.decode("utf-8", errors="replace")
    out_path.write_text(text, encoding="utf-8")
    return text


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_dom(text: str) -> Node:
    parser = TreeParser()
    parser.feed(text)
    return parser.root


def int_attr(node: Node, name: str, default: int = 1) -> int:
    raw = node.attrs.get(name, "")
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def expand_table(table: Node) -> list[list[dict[str, Any]]]:
    rows = table.find_all("tr")
    matrix: list[list[dict[str, Any]]] = []
    spans: dict[int, tuple[int, dict[str, Any]]] = {}
    for row_index, row in enumerate(rows):
        out: list[dict[str, Any]] = []
        col = 0

        def fill_spans() -> None:
            nonlocal col
            while col in spans:
                remaining, cell = spans[col]
                inherited = dict(cell)
                inherited["origin"] = "inherited_rowspan"
                out.append(inherited)
                if remaining <= 1:
                    del spans[col]
                else:
                    spans[col] = (remaining - 1, cell)
                col += 1

        fill_spans()
        direct_cells = [c for c in row.children if c.tag in {"td", "th"}]
        for cell_node in direct_cells:
            fill_spans()
            rowspan = int_attr(cell_node, "rowspan")
            colspan = int_attr(cell_node, "colspan")
            cell = {
                "tag": cell_node.tag,
                "text": cell_node.text(),
                "node": cell_node,
                "rowspan": rowspan,
                "colspan": colspan,
                "origin": "direct",
                "row_index": row_index,
                "column_index": col,
            }
            for offset in range(colspan):
                placed = dict(cell)
                placed["column_index"] = col + offset
                if offset:
                    placed["origin"] = "direct_colspan"
                out.append(placed)
                if rowspan > 1:
                    spans[col + offset] = (rowspan - 1, placed)
            col += colspan
        fill_spans()
        if out:
            matrix.append(out)
    return matrix


def normalize_headers(row: list[dict[str, Any]]) -> list[str]:
    headers = []
    for cell in row:
        text = cell["text"].replace("No.", "wiki_no")
        text = text.replace("名前", "name")
        text = text.replace("タイプ", "type")
        text = text.replace("属性", "attribute")
        text = text.replace("色", "color")
        text = text.replace("スキル", "skill_name")
        text = text.replace("VU対応", "vu_marker")
        text = text.replace("備考", "remarks")
        if not text:
            text = "image"
        headers.append(text)
    return headers


def is_denko_id(value: str, pool: str) -> bool:
    if pool == "original":
        return bool(re.fullmatch(r"\d+", value))
    return bool(re.fullmatch(r"EX\d+", value))


def normalize_denko_id(wiki_no: str, pool: str) -> tuple[str, int | None]:
    if pool == "original":
        n = int(wiki_no)
        return f"original:{n:03d}", n
    n = int(wiki_no.replace("EX", ""))
    return f"extra:{n:03d}", n


def extract_attribute(cell_text: str) -> str | None:
    for attr in ("heat", "eco", "cool", "flat"):
        if re.search(rf"\b{attr}\b", cell_text):
            return attr
    return cell_text or None


def source_meta(url: str, content_hash: str, authority: str, confidence: str = "medium") -> dict[str, Any]:
    return {
        "source_url": url,
        "source_authority": authority,
        "content_hash": content_hash,
        "parser_version": PARSER_VERSION,
        "parsed_at": datetime.now(JST).isoformat(),
        "confidence": confidence,
        "needs_review": confidence != "high",
        "review_reasons": [] if confidence == "high" else ["sample_parse_needs_human_review"],
    }


def parse_list_page(pool: str, url: str, html_text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    root = parse_dom(html_text)
    tables = root.find_all("table")
    records: list[dict[str, Any]] = []
    reviews: list[dict[str, Any]] = []
    html_hash = sha256_text(html_text)
    for table_index, table in enumerate(tables):
        matrix = expand_table(table)
        header: list[str] | None = None
        for row_index, row in enumerate(matrix):
            row_text = [c["text"] for c in row]
            joined = " ".join(row_text)
            if "No." in joined and "名前" in joined and "タイプ" in joined:
                header = normalize_headers(row)
                continue
            if not header or not row:
                continue
            if len(row) < len(header):
                continue
            cells = {header[i]: row[i] for i in range(min(len(header), len(row)))}
            wiki_no = cells.get("wiki_no", {}).get("text", "")
            if not is_denko_id(wiki_no, pool):
                continue
            denko_id, id_number = normalize_denko_id(wiki_no, pool)
            name_cell = cells.get("name")
            link = name_cell["node"].first_link() if name_cell else {"href": None, "title": None, "text": None}
            name = link.get("text") or (name_cell["text"] if name_cell else "")
            detail_url = urljoin(BASE_URL, link["href"]) if link.get("href") else None
            required_missing = [
                key
                for key in ("wiki_no", "name", "type", "attribute", "color", "skill_name")
                if not cells.get(key, {}).get("text")
            ]
            confidence = "high" if detail_url and not required_missing else "low"
            record = {
                "record_meta": source_meta(url, html_hash, "denko_list", confidence),
                "identity": {
                    "denko_id": denko_id,
                    "wiki_no": wiki_no,
                    "id_pool": pool,
                    "id_number": id_number,
                    "name": name,
                    "full_name": name,
                    "aliases": [],
                    "number": f"No.{id_number}" if pool == "original" else f"EX No.{id_number}",
                    "wiki_page_title": link.get("title"),
                    "pool": pool,
                    "detail_url": detail_url,
                    "type": cells.get("type", {}).get("text") or None,
                    "attribute": extract_attribute(cells.get("attribute", {}).get("text", "")),
                    "color": cells.get("color", {}).get("text") or None,
                },
                "list_page_fields": {
                    "skill_name": cells.get("skill_name", {}).get("text") or None,
                    "vu_marker": cells.get("vu_marker", {}).get("text") or None,
                    "remarks": cells.get("remarks", {}).get("text") or None,
                    "cell_origin_by_column": {key: cell.get("origin") for key, cell in cells.items()},
                    "table_index": table_index,
                    "row_index": row[0].get("row_index"),
                },
                "growth": {
                    "level_cap": None,
                    "is_vu_available": (cells.get("vu_marker", {}).get("text") == "◆"),
                    "vu_changes": [],
                    "mileage_final_ap": None,
                    "mileage_final_hp": None,
                },
                "skills": [],
                "summary_zh": None,
            }
            if required_missing:
                reviews.append(review_item(record, "identity", f"missing required fields: {required_missing}"))
            records.append(record)
    return records[:5], reviews


def review_item(record: dict[str, Any], field_path: str, reason: str) -> dict[str, Any]:
    ident = record.get("identity", {})
    return {
        "record_meta": record["record_meta"],
        "review_id": f"sample-{ident.get('denko_id', 'unknown')}-{field_path}",
        "entity_ref": {
            "denko_id": ident.get("denko_id"),
            "name": ident.get("name"),
            "detail_url": ident.get("detail_url"),
        },
        "field_path": field_path,
        "reason": reason,
        "severity": "warning",
        "evidence": {
            "source_section": "list_page",
            "table_index": record.get("list_page_fields", {}).get("table_index"),
            "row_index": record.get("list_page_fields", {}).get("row_index"),
            "column_name": None,
            "raw_html_snippet": None,
            "text_snippet": None,
            "screenshot_path": None,
            "cell_origin_by_column": record.get("list_page_fields", {}).get("cell_origin_by_column", {}),
        },
        "status": "open",
    }


def detail_summary(url: str, html_text: str) -> dict[str, Any]:
    root = parse_dom(html_text)
    headings = []
    for tag in ("h1", "h2", "h3"):
        for node in root.find_all(tag):
            text = node.text()
            if text:
                headings.append({"tag": tag, "text": text})
    tables = root.find_all("table")
    rowspans = len(re.findall(r"rowspan", html_text))
    colspans = len(re.findall(r"colspan", html_text))
    title = headings[0]["text"] if headings else None
    skill_like_tables = []
    for i, table in enumerate(tables):
        text = table.text()
        if any(key in text for key in ("スキル", "効果", "発動率", "Lv.")):
            matrix = expand_table(table)
            skill_like_tables.append(
                {
                    "table_index": i,
                    "row_count": len(matrix),
                    "first_rows": [[c["text"] for c in row[:5]] for row in matrix[:3]],
                }
            )
    return {
        "detail_title": title,
        "detail_hash": sha256_text(html_text),
        "table_count": len(tables),
        "rowspan_count": rowspans,
        "colspan_count": colspans,
        "headings": headings[:12],
        "skill_like_tables": skill_like_tables[:3],
        "needs_table_matrix": bool(rowspans or colspans or len(tables) > 1),
        "source_url": url,
    }


def enrich_details(records: list[dict[str, Any]], reviews: list[dict[str, Any]]) -> None:
    for record in records:
        ident = record["identity"]
        detail_url = ident.get("detail_url")
        if not detail_url:
            reviews.append(review_item(record, "identity.detail_url", "missing detail_url"))
            continue
        raw_path = RAW_DIR / f"sample_detail_{ident['denko_id'].replace(':', '_')}.html"
        detail_html = fetch(detail_url, raw_path)
        summary = detail_summary(detail_url, detail_html)
        record["detail_page_probe"] = summary
        if summary["needs_table_matrix"]:
            record.setdefault("parse_notes", []).append("detail_page_has_complex_tables")
        if summary["detail_title"] and summary["detail_title"] != ident["name"]:
            record["identity"]["full_name"] = summary["detail_title"]


def build_skill_fact_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        ident = record["identity"]
        detail = record.get("detail_page_probe", {})
        skill_detail = extract_skill_detail(record)
        key_level_stats = extract_key_level_stats(record)
        review_reasons = []
        if not skill_detail.get("lv50"):
            review_reasons.append("lv50_skill_row_not_found")
        if not key_level_stats:
            review_reasons.append("key_level_stats_not_found")
        review_reasons.append("sample_parse_needs_human_review")
        meta = source_meta(
            detail.get("source_url") or ident.get("detail_url"),
            detail.get("detail_hash"),
            "detail_page",
            "medium" if skill_detail else "low",
        )
        meta["needs_review"] = True
        meta["review_reasons"] = review_reasons
        normalized_skill = skill_detail.get("normalized_skill")
        lv50 = skill_detail.get("lv50")
        values_by_denko_level = skill_detail.get("values_by_denko_level")
        rows.append(
            {
                "record_meta": meta,
                "denko_id": ident["denko_id"],
                "name": ident["name"],
                "pool": ident["pool"],
                "skill_name": record.get("list_page_fields", {}).get("skill_name"),
                "detail_url": ident.get("detail_url"),
                "trigger_condition": skill_detail.get("trigger_condition"),
                "activation_type": skill_detail.get("activation_type"),
                "skill_remarks": skill_detail.get("skill_remarks"),
                "effect_summary": skill_detail.get("effect_summary"),
                "normalized_skill": normalized_skill,
                "lv50": lv50,
                "values_by_denko_level": values_by_denko_level,
                "key_level_stats": key_level_stats,
                "source_tables": skill_detail.get("source_tables"),
                "skill_table_candidates": detail.get("skill_like_tables", []),
                "summary_zh": build_summary_zh(normalized_skill, lv50, values_by_denko_level),
                "note_zh": "样本阶段已抽取核心技能字段和关键 AP/HP 节点，仍需人工复核复杂表格。",
            }
        )
    return rows


def table_dicts(matrix: list[list[dict[str, Any]]]) -> tuple[list[str], list[dict[str, str]]]:
    if not matrix:
        return [], []
    headers = [cell["text"] for cell in matrix[0]]
    rows: list[dict[str, str]] = []
    for row in matrix[1:]:
        item: dict[str, str] = {}
        for i, header in enumerate(headers):
            if not header:
                header = f"column_{i}"
            item[header] = row[i]["text"] if i < len(row) else ""
        rows.append(item)
    return headers, rows


def find_detail_tables(record: dict[str, Any]) -> list[tuple[int, list[str], list[dict[str, str]]]]:
    ident = record["identity"]
    raw_path = RAW_DIR / f"sample_detail_{ident['denko_id'].replace(':', '_')}.html"
    if not raw_path.exists():
        return []
    root = parse_dom(raw_path.read_text(encoding="utf-8", errors="replace"))
    found = []
    for i, table in enumerate(root.find_all("table")):
        headers, rows = table_dicts(expand_table(table))
        if headers:
            found.append((i, headers, rows))
    return found


def extract_skill_detail(record: dict[str, Any]) -> dict[str, Any]:
    tables = find_detail_tables(record)
    condition_table = None
    skill_level_table = None
    for table_index, headers, rows in tables:
        header_text = " ".join(headers)
        if not condition_table and "アクティベーションタイプ" in header_text and any(h in header_text for h in ["発動条件", "発動条件・効果", "効果"]):
            condition_table = (table_index, headers, rows)
        if not skill_level_table and "スキルLv" in header_text and any("でんこLv" in (row.get("スキルLv", "") or "") for row in rows):
            skill_level_table = (table_index, headers, rows)
    if not condition_table and not skill_level_table:
        return {}

    trigger_condition = None
    activation_type = None
    skill_remarks = None
    effect_summary = None
    condition_table_index = None
    if condition_table:
        condition_table_index, headers, rows = condition_table
        if rows:
            trigger_condition = join_unique_values(rows, ["発動条件"])
            combined_condition_effect = join_unique_values(rows, ["発動条件・効果"])
            if not trigger_condition:
                trigger_condition = combined_condition_effect
            effect_summary = join_unique_values(rows, ["効果"]) or combined_condition_effect
            activation_type = join_unique_values(rows, ["アクティベーションタイプ"])
            skill_remarks = join_unique_values(rows, ["備考"])

    lv50 = None
    values_by_denko_level: dict[str, dict[str, Any]] = {}
    skill_level_table_index = None
    if skill_level_table:
        skill_level_table_index, headers, rows = skill_level_table
        for row in rows:
            denko_level = parse_denko_level(row.get("スキルLv", ""))
            if not denko_level:
                continue
            values_by_denko_level[denko_level] = skill_level_row_fact(headers, row)
        candidates = [row for row in rows if re.search(r"でんこLv\.?\s*50", row.get("スキルLv", ""))]
        if not candidates:
            candidates = [row for row in rows if row.get("スキルLv", "").startswith("Lv.4")]
        if candidates:
            lv50 = skill_level_row_fact(headers, candidates[0])

    return {
        "trigger_condition": trigger_condition,
        "activation_type": activation_type,
        "skill_remarks": skill_remarks,
        "effect_summary": effect_summary,
        "normalized_skill": normalize_skill_semantics(trigger_condition, effect_summary, activation_type, values_by_denko_level),
        "lv50": lv50,
        "values_by_denko_level": values_by_denko_level,
        "source_tables": {
            "condition_table_index": condition_table_index,
            "skill_level_table_index": skill_level_table_index,
        },
    }


def first_matching_value(row: dict[str, str], names: list[str]) -> str | None:
    for name in names:
        for key, value in row.items():
            if name in key and value:
                return value
    return None


def parse_denko_level(skill_level: str) -> str | None:
    match = re.search(r"でんこLv\.?\s*(\d+)", skill_level)
    return match.group(1) if match else None


def skill_level_row_fact(headers: list[str], row: dict[str, str]) -> dict[str, Any]:
    probability = {h: row.get(h, "") for h in headers if "発動率" in h and row.get(h)}
    duration = first_matching_value(row, ["効果時間", "発動時間"])
    cooldown = first_matching_value(row, ["クールタイム", "CD"])
    return {
        "skill_level": row.get("スキルLv"),
        "denko_level": parse_denko_level(row.get("スキルLv", "")),
        "special_explanation": row.get("コメント"),
        "effect": row.get("効果"),
        "duration": duration,
        "cooldown": cooldown,
        "probability": probability,
        "raw_row": row,
    }


def normalize_skill_semantics(
    trigger_condition: str | None,
    effect_summary: str | None,
    activation_type: str | None,
    values_by_denko_level: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    text = " ".join(value for value in [trigger_condition, effect_summary] if value)
    effect_kind: list[str] = []
    target_scope: list[str] = []
    trigger: dict[str, Any] = {}
    confidence = "low"
    review_reasons: list[str] = []

    if "HPを回復" in text or "回復" in text:
        effect_kind.append("hp_recovery")
    if "フットバー" in text:
        effect_kind.append("footbar")
    if "DEF" in text:
        effect_kind.append("def_modifier")
    if "追加アクセス" in text:
        effect_kind.append("extra_access")
    if "スキル無効化" in text:
        effect_kind.append("skill_disable")
    if "経験値" in text:
        effect_kind.append("exp_gain")
    if "固定ダメージ" in text:
        effect_kind.append("fixed_damage")
    if "ダメージ軽減" in text:
        effect_kind.append("damage_reduction")
    if "思い出しアクセス" in text:
        effect_kind.append("memory_access_boost")

    if "編成内でんこ" in text or "編成内のでんこ" in text or "編成内の全てのでんこ" in text:
        target_scope.append("team_all")
    elif "自身" in text or "自分" in text:
        target_scope.append("self")

    hp_threshold = re.search(r"HPが(\d+)%以下", text)
    if hp_threshold:
        trigger["hp_threshold_percent"] = int(hp_threshold.group(1))
        trigger["operator"] = "lte"

    if "マスターにおまかせ" in (activation_type or ""):
        activation_mode = "passive_auto"
    elif "いつでもアクティブ" in (activation_type or ""):
        activation_mode = "always_active"
    else:
        activation_mode = None
        review_reasons.append("unknown_activation_type")

    if effect_kind and (target_scope or trigger):
        confidence = "medium"
    else:
        review_reasons.append("semantic_rule_not_enough")

    return {
        "effect_kind": effect_kind,
        "target_scope": target_scope,
        "trigger": trigger,
        "activation_mode": activation_mode,
        "confidence": confidence,
        "review_reasons": review_reasons,
        "available_denko_levels": sorted(values_by_denko_level.keys(), key=lambda x: int(x)),
    }


def build_summary_zh(
    normalized_skill: dict[str, Any] | None,
    lv50: dict[str, Any] | None,
    values_by_denko_level: dict[str, dict[str, Any]] | None,
) -> str | None:
    if not normalized_skill:
        return None
    effect_labels = {
        "hp_recovery": "HP回复",
        "footbar": "フットバー",
        "def_modifier": "DEF变化",
        "extra_access": "追加访问",
        "skill_disable": "技能无效化",
        "exp_gain": "经验值获得",
        "fixed_damage": "固定伤害",
        "damage_reduction": "伤害减轻",
        "memory_access_boost": "思い出しアクセス强化",
    }
    target_labels = {
        "team_all": "编成内全员",
        "self": "自身",
    }
    parts = []
    effect_kind = normalized_skill.get("effect_kind") or []
    if effect_kind:
        parts.append("技能：" + "、".join(effect_labels.get(kind, kind) for kind in effect_kind))
    trigger = normalized_skill.get("trigger") or {}
    if trigger.get("hp_threshold_percent") is not None:
        parts.append(f"条件：HP{trigger['hp_threshold_percent']}%以下")
    target_scope = normalized_skill.get("target_scope") or []
    if target_scope:
        parts.append("对象：" + "、".join(target_labels.get(target, target) for target in target_scope))
    if lv50:
        parts.append("Lv50：" + compact_skill_level_zh(lv50))
    lv60 = (values_by_denko_level or {}).get("60")
    if lv60:
        parts.append("Lv60：" + compact_skill_level_zh(lv60))
    return "；".join(parts) if parts else None


def compact_skill_level_zh(row: dict[str, Any]) -> str:
    parts = []
    if row.get("effect"):
        parts.append(row["effect"])
    probability = row.get("probability") or {}
    if probability:
        parts.append("，".join(f"{key} {value}" for key, value in probability.items()))
    if row.get("duration"):
        parts.append(row["duration"])
    if row.get("cooldown"):
        parts.append(f"CD {row['cooldown']}")
    return "，".join(parts)


def join_unique_values(rows: list[dict[str, str]], keys: list[str]) -> str | None:
    values: list[str] = []
    for row in rows:
        for key in keys:
            value = row.get(key)
            if value and value not in values:
                values.append(value)
    return " / ".join(values) if values else None


def extract_key_level_stats(record: dict[str, Any]) -> dict[str, dict[str, str]]:
    target_levels = {"15", "30", "50", "60", "70", "80"}
    best: tuple[int, list[dict[str, str]]] | None = None
    for table_index, headers, rows in find_detail_tables(record):
        if {"Lv", "AP", "HP"}.issubset(set(headers)):
            if not best or len(rows) > len(best[1]):
                best = (table_index, rows)
    if not best:
        return {}
    table_index, rows = best
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        lv = row.get("Lv")
        if lv in target_levels:
            out[lv] = {
                "AP": row.get("AP", ""),
                "HP": row.get("HP", ""),
                "Exp": row.get("Exp", ""),
                "source_table_index": str(table_index),
            }
    return out


def build_skill_review_items(skill_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reviews: list[dict[str, Any]] = []
    for row in skill_rows:
        reason = "sample skill fact needs human review"
        if not row.get("lv50"):
            reason = "Lv50 skill row not found or not applicable"
        reviews.append(
            {
                "record_meta": row["record_meta"],
                "review_id": f"sample-{row['denko_id']}-skill_fact",
                "entity_ref": {
                    "denko_id": row["denko_id"],
                    "name": row["name"],
                    "detail_url": row["detail_url"],
                },
                "field_path": "skill_fact",
                "reason": reason,
                "severity": "info",
                "evidence": {
                    "source_section": "detail_page_probe",
                    "table_index": None,
                    "row_index": None,
                    "column_name": None,
                    "raw_html_snippet": None,
                    "text_snippet": None,
                    "screenshot_path": None,
                    "cell_origin_by_column": {},
                },
                "status": "open",
            }
        )
    return reviews


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def write_report(records: list[dict[str, Any]], skill_rows: list[dict[str, Any]], reviews: list[dict[str, Any]]) -> None:
    def esc(value: Any) -> str:
        return html.escape("" if value is None else str(value))

    lines = [
        "<!doctype html>",
        '<html lang="zh-CN">',
        "<head>",
        '  <meta charset="utf-8">',
        "  <title>Sample First 5 Denko Report</title>",
        "  <style>",
        "    body { font-family: system-ui, sans-serif; line-height: 1.5; margin: 24px; }",
        "    table { border-collapse: collapse; width: 100%; margin: 12px 0 24px; }",
        "    th, td { border: 1px solid #ccc; padding: 6px 8px; vertical-align: top; }",
        "    th { background: #f5f5f5; }",
        "    code { background: #f6f8fa; padding: 1px 4px; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <h1>Sample First 5 Denko Report</h1>",
        "  <p>本次测试抓取 Original 前 5 与 Extra 前 5。结构化事实保留日语原文，说明层使用中文。</p>",
        "  <h2>结构化结果摘要</h2>",
    ]
    for pool in ("original", "extra"):
        lines.append(f"  <h3>{esc(pool)}</h3>")
        lines.append("  <table>")
        lines.append("    <thead><tr><th>denko_id</th><th>wiki_no</th><th>name</th><th>type</th><th>attribute</th><th>color</th><th>skill_name</th><th>VU</th><th>summary_zh</th><th>effect kind</th><th>target</th><th>trigger</th><th>effect summary</th><th>Lv50 effect</th><th>activation</th><th>condition</th><th>duration</th><th>CD</th><th>probability</th><th>remarks</th></tr></thead>")
        lines.append("    <tbody>")
        for record in [r for r in records if r["identity"]["pool"] == pool]:
            ident = record["identity"]
            fields = record["list_page_fields"]
            skill = next((s for s in skill_rows if s["denko_id"] == ident["denko_id"]), {})
            lv50 = skill.get("lv50") or {}
            normalized = skill.get("normalized_skill") or {}
            lines.append(
                "      <tr>"
                f"<td>{esc(ident['denko_id'])}</td>"
                f"<td>{esc(ident['wiki_no'])}</td>"
                f"<td>{esc(ident['name'])}</td>"
                f"<td>{esc(ident.get('type'))}</td>"
                f"<td>{esc(ident.get('attribute'))}</td>"
                f"<td>{esc(ident.get('color'))}</td>"
                f"<td>{esc(fields.get('skill_name'))}</td>"
                f"<td>{esc(fields.get('vu_marker'))}</td>"
                f"<td>{esc(skill.get('summary_zh'))}</td>"
                f"<td>{esc(', '.join(normalized.get('effect_kind') or []))}</td>"
                f"<td>{esc(', '.join(normalized.get('target_scope') or []))}</td>"
                f"<td>{esc(json.dumps(normalized.get('trigger') or {}, ensure_ascii=False))}</td>"
                f"<td>{esc(skill.get('effect_summary'))}</td>"
                f"<td>{esc(lv50.get('effect'))}</td>"
                f"<td>{esc(skill.get('activation_type'))}</td>"
                f"<td>{esc(skill.get('trigger_condition'))}</td>"
                f"<td>{esc(lv50.get('duration'))}</td>"
                f"<td>{esc(lv50.get('cooldown'))}</td>"
                f"<td>{esc(json.dumps(lv50.get('probability'), ensure_ascii=False) if lv50.get('probability') else '')}</td>"
                f"<td>{esc(skill.get('skill_remarks'))}</td>"
                "</tr>"
            )
        lines.append("    </tbody>")
        lines.append("  </table>")
    lines.append("  <h2>技能等级值</h2>")
    for pool in ("original", "extra"):
        lines.append(f"  <h3>{esc(pool)}</h3>")
        lines.append("  <table>")
        lines.append("    <thead><tr><th>denko_id</th><th>name</th><th>Lv50</th><th>Lv60</th><th>Lv70</th><th>Lv80</th><th>Lv92</th><th>Lv96</th><th>Lv100</th></tr></thead>")
        lines.append("    <tbody>")
        for skill in [s for s in skill_rows if s["pool"] == pool]:
            values = skill.get("values_by_denko_level", {})
            def skill_cell(lv: str) -> str:
                row = values.get(lv)
                if not row:
                    return ""
                parts = []
                if row.get("effect"):
                    parts.append(row["effect"])
                if row.get("probability"):
                    parts.append(json.dumps(row["probability"], ensure_ascii=False))
                if row.get("duration"):
                    parts.append(f"time {row['duration']}")
                if row.get("cooldown"):
                    parts.append(f"CD {row['cooldown']}")
                return " / ".join(parts)
            lines.append(
                "      <tr>"
                f"<td>{esc(skill['denko_id'])}</td>"
                f"<td>{esc(skill['name'])}</td>"
                f"<td>{esc(skill_cell('50'))}</td>"
                f"<td>{esc(skill_cell('60'))}</td>"
                f"<td>{esc(skill_cell('70'))}</td>"
                f"<td>{esc(skill_cell('80'))}</td>"
                f"<td>{esc(skill_cell('92'))}</td>"
                f"<td>{esc(skill_cell('96'))}</td>"
                f"<td>{esc(skill_cell('100'))}</td>"
                "</tr>"
            )
        lines.append("    </tbody>")
        lines.append("  </table>")
    lines.append("  <h2>关键 AP/HP 节点</h2>")
    for pool in ("original", "extra"):
        lines.append(f"  <h3>{esc(pool)}</h3>")
        lines.append("  <table>")
        lines.append("    <thead><tr><th>denko_id</th><th>name</th><th>Lv15</th><th>Lv30</th><th>Lv50</th><th>Lv60</th><th>Lv70</th><th>Lv80</th></tr></thead>")
        lines.append("    <tbody>")
        for skill in [s for s in skill_rows if s["pool"] == pool]:
            nodes = skill.get("key_level_stats", {})
            def cell(lv: str) -> str:
                node = nodes.get(lv)
                return f"AP {node.get('AP')} / HP {node.get('HP')}" if node else ""
            lines.append(
                "      <tr>"
                f"<td>{esc(skill['denko_id'])}</td>"
                f"<td>{esc(skill['name'])}</td>"
                f"<td>{esc(cell('15'))}</td>"
                f"<td>{esc(cell('30'))}</td>"
                f"<td>{esc(cell('50'))}</td>"
                f"<td>{esc(cell('60'))}</td>"
                f"<td>{esc(cell('70'))}</td>"
                f"<td>{esc(cell('80'))}</td>"
                "</tr>"
            )
        lines.append("    </tbody>")
        lines.append("  </table>")
    lines.extend(
        [
            "  <h2>中文解释</h2>",
            "  <ul>",
            "    <li>ID 映射可从列表页稳定抽取：Original 规范化为 <code>original:NNN</code>，Extra 规范化为 <code>extra:NNN</code>。</li>",
            "    <li>Original 样本中 No.1 起的 <code>備考</code> 使用了继承单元格，证明 table matrix 展开是必要的。</li>",
            "    <li>详情页技能表已抽取 Lv50 効果、特殊条件、アクティベーションタイプ、効果時間、CD、発動率、備考；仍需人工复核复杂模板。</li>",
            f"    <li>skill_fact 样本条目数：{len(skill_rows)}，当前标记为 needs_review，以便确认复杂表格和特殊模板。</li>",
            "    <li>本次没有启动 solver，也没有导入推荐页 prior 或 observed team case。</li>",
            f"    <li>review_queue 条目数：{len(reviews)}。</li>",
            "  </ul>",
            "  <h2>输出文件</h2>",
            "  <ul>",
            "    <li><code>data/records/sample_first5_denko_facts.jsonl</code></li>",
            "    <li><code>data/records/sample_first5_skill_facts.jsonl</code></li>",
            "    <li><code>data/indexes/sample_first5_denko_index.json</code></li>",
            "    <li><code>data/review_queue/sample_first5_review_queue.jsonl</code></li>",
            "    <li><code>data/reports/sample_first5_report_zh.html</code></li>",
            "  </ul>",
            "</body>",
            "</html>",
        ]
    )
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "sample_first5_report_zh.html").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    all_records: list[dict[str, Any]] = []
    all_reviews: list[dict[str, Any]] = []
    for pool, url in LIST_PAGES.items():
        raw_path = RAW_DIR / f"sample_{pool}_list.html"
        html_text = fetch(url, raw_path)
        records, reviews = parse_list_page(pool, url, html_text)
        enrich_details(records, reviews)
        all_records.extend(records)
        all_reviews.extend(reviews)

    skill_rows = build_skill_fact_records(all_records)
    all_reviews.extend(build_skill_review_items(skill_rows))

    index = {
        "schema_version": 1,
        "parser_version": PARSER_VERSION,
        "generated_at": datetime.now(JST).isoformat(),
        "sample_scope": {"original": 5, "extra": 5},
        "records": [
            {
                "denko_id": r["identity"]["denko_id"],
                "wiki_no": r["identity"]["wiki_no"],
                "name": r["identity"]["name"],
                "pool": r["identity"]["pool"],
                "detail_url": r["identity"]["detail_url"],
            }
            for r in all_records
        ],
    }
    write_jsonl(RECORD_DIR / "sample_first5_denko_facts.jsonl", all_records)
    write_jsonl(RECORD_DIR / "sample_first5_skill_facts.jsonl", skill_rows)
    write_jsonl(REVIEW_DIR / "sample_first5_review_queue.jsonl", all_reviews)
    (INDEX_DIR / "sample_first5_denko_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    write_report(all_records, skill_rows, all_reviews)
    print(json.dumps({"denko_records": len(all_records), "skill_records": len(skill_rows), "reviews": len(all_reviews)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
