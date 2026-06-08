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
PARSER_VERSION = "detail_html_table_matrix.v8"
KEY_DENKO_LEVELS = ("1", "15", "30", "50", "60", "70", "80", "92", "96", "100")
DEFAULT_FOCUS_LEVELS = ("30", "50")
VU_LEVELS = ("92", "96", "100")

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


def parse_list_page(
    pool: str,
    url: str,
    html_text: str,
    limit: int | None = 5,
    id_min: int | None = None,
    id_max: int | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
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
    if id_min is not None or id_max is not None:
        records = [
            record
            for record in records
            if record["identity"].get("id_number") is not None
            and (id_min is None or record["identity"]["id_number"] >= id_min)
            and (id_max is None or record["identity"]["id_number"] <= id_max)
        ]
    if limit is not None:
        records = records[:limit]
    return records, reviews


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
        skill_components = skill_detail.get("skill_components")
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
                "skill_components": skill_components,
                "lv50": lv50,
                "values_by_denko_level": values_by_denko_level,
                "key_level_stats": key_level_stats,
                "source_tables": skill_detail.get("source_tables"),
                "skill_table_candidates": detail.get("skill_like_tables", []),
                "summary_zh": build_summary_zh(skill_components, normalized_skill, lv50, values_by_denko_level),
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
    if not values_by_denko_level:
        flat_values = extract_flat_skill_values(tables)
        if flat_values:
            values_by_denko_level.update(flat_values)
    merge_seasonal_skill_values(values_by_denko_level, tables)

    skill_components = build_skill_components(
        trigger_condition,
        effect_summary,
        activation_type,
        skill_remarks,
        values_by_denko_level,
    )
    return {
        "trigger_condition": trigger_condition,
        "activation_type": activation_type,
        "skill_remarks": skill_remarks,
        "effect_summary": effect_summary,
        "normalized_skill": normalize_skill_semantics(trigger_condition, effect_summary, activation_type, values_by_denko_level),
        "skill_components": skill_components,
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
    effect = row.get("効果") or " ".join(
        effect_cell_text(h, row.get(h, ""))
        for h in headers
        if is_effect_value_header(h) and row.get(h)
    )
    return {
        "skill_level": row.get("スキルLv"),
        "denko_level": parse_denko_level(row.get("スキルLv", "")),
        "special_explanation": row.get("コメント"),
        "effect": effect or None,
        "duration": duration,
        "cooldown": cooldown,
        "probability": probability,
        "raw_row": row,
    }


def is_effect_value_header(header: str) -> bool:
    if "効果" not in header:
        return False
    return not any(excluded in header for excluded in ["効果時間", "発動時間", "効果範囲"])


def effect_cell_text(header: str, value: str) -> str:
    if not value:
        return ""
    if re.search(r"[\(（]\d+[\)）]", value):
        return value
    labels = re.findall(r"[\(（](\d+)[\)）]", header)
    if len(labels) == 1:
        return f"({labels[0]}) {value}"
    return value


def extract_flat_skill_values(tables: list[tuple[int, list[str], list[dict[str, str]]]]) -> dict[str, dict[str, Any]]:
    for _table_index, headers, rows in tables:
        if "効果" not in headers or "スキルLv" in headers:
            continue
        if not any(header in headers for header in ["効果時間", "発動時間", "クールタイム", "発動率"]):
            continue
        if not rows:
            continue
        return {"base": skill_level_row_fact(headers, rows[0]) | {"denko_level": "base"}}
    return {}


def merge_seasonal_skill_values(
    values_by_denko_level: dict[str, dict[str, Any]],
    tables: list[tuple[int, list[str], list[dict[str, str]]]],
) -> None:
    seasonal = extract_seasonal_skill_values(tables)
    if not seasonal:
        return
    for level, seasonal_values in seasonal.items():
        if level in values_by_denko_level:
            values_by_denko_level[level]["seasonal_values"] = seasonal_values
    if "80" in seasonal:
        for level, row_fact in values_by_denko_level.items():
            if level in VU_LEVELS and "seasonal_values" not in row_fact:
                row_fact["seasonal_values"] = seasonal["80"]


def extract_seasonal_skill_values(
    tables: list[tuple[int, list[str], list[dict[str, str]]]]
) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    required = ["経験値付与", "固定ダメージ", "スコア獲得", "ダメージ軽減"]
    for _table_index, headers, rows in tables:
        if "スキルLv" not in headers:
            continue
        if not all(any(required_name in header for header in headers) for required_name in required):
            continue
        for row in rows:
            level = parse_denko_level(row.get("スキルLv", ""))
            if not level:
                continue
            out[level] = {
                "exp_gain": first_matching_value(row, ["経験値付与"]) or "",
                "fixed_damage": first_matching_value(row, ["固定ダメージ"]) or "",
                "score_gain": first_matching_value(row, ["スコア獲得"]) or "",
                "damage_reduction": first_matching_value(row, ["ダメージ軽減"]) or "",
            }
    return out


def build_skill_components(
    trigger_condition: str | None,
    effect_summary: str | None,
    activation_type: str | None,
    skill_remarks: str | None,
    values_by_denko_level: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    common_text = join_unique_text([trigger_condition, effect_summary])
    condition_context = join_unique_text([trigger_condition, effect_summary, skill_remarks])
    components: dict[str, dict[str, Any]] = {}
    for denko_level, row_fact in values_by_denko_level.items():
        for parsed in parse_level_components(common_text, row_fact):
            if not parsed.get("condition_label"):
                inferred_label = infer_condition_label_for_effect(common_text, parsed["effect_kind"])
                if inferred_label:
                    parsed["condition_label"] = inferred_label
                    parsed["component_id"] = f"{parsed['effect_kind']}_{inferred_label.strip('()')}"
                    parsed["effect_role"] = effect_role_from_label(inferred_label, common_text)
                    parsed["value"]["probability"] = probability_for_label(
                        parsed["value"].get("raw_row", {}).get("probability", {})
                        or parsed["value"].get("probability", {}),
                        inferred_label,
                    )
            component_id = parsed["component_id"]
            component_condition = component_condition_text(condition_context, parsed)
            component = components.setdefault(
                component_id,
                {
                    "component_id": component_id,
                    "effect_kind": parsed["effect_kind"],
                    "effect_role": parsed.get("effect_role"),
                    "condition_label": parsed.get("condition_label"),
                    "target_scope": parsed.get("target_scope")
                    or infer_target_scope(component_condition, parsed["effect_kind"])
                    or infer_target_scope(common_text, parsed["effect_kind"]),
                    "target_filters": parsed.get("target_filters")
                    or infer_target_filters(component_condition, parsed["effect_kind"]),
                    "trigger_conditions": parsed.get("trigger_conditions")
                    or infer_trigger_conditions(component_condition, parsed["effect_kind"]),
                    "scaling_conditions": infer_scaling_conditions(component_condition),
                    "activation_type": activation_type,
                    "condition_raw": component_condition or trigger_condition or effect_summary,
                    "remarks_raw": skill_remarks,
                    "values_by_denko_level": {},
                    "confidence": "medium",
                    "needs_review": True,
                    "review_reasons": ["component_semantics_need_review"],
                },
            )
            adjust_component_semantics(component, common_text)
            enrich_component_from_value_text(component, parsed["value"].get("source_text"))
            component["values_by_denko_level"][denko_level] = parsed["value"]
    add_condition_only_components(components, condition_context, activation_type, values_by_denko_level)
    drop_unlabeled_duplicates_when_labeled_exists(components)
    for parsed in parse_probability_boost_components(common_text, values_by_denko_level):
        component_id = parsed["component_id"]
        component_condition = component_condition_text(condition_context, parsed)
        component = components.setdefault(
            component_id,
            {
                "component_id": component_id,
                "effect_kind": parsed["effect_kind"],
                "condition_label": parsed.get("condition_label"),
                "effect_role": effect_role_from_label(parsed.get("condition_label"), common_text)
                if parsed.get("condition_label")
                else None,
                "target_scope": infer_target_scope(component_condition, parsed["effect_kind"]),
                "target_filters": infer_target_filters(component_condition, parsed["effect_kind"]),
                "trigger_conditions": infer_trigger_conditions(component_condition, parsed["effect_kind"]),
                "activation_type": activation_type,
                "condition_raw": component_condition or trigger_condition or effect_summary,
                "remarks_raw": skill_remarks,
                "values_by_denko_level": {},
                "confidence": "medium",
                "needs_review": True,
                "review_reasons": ["component_semantics_need_review", "vu_probability_modifier"],
            },
        )
        adjust_component_semantics(component, common_text)
        enrich_component_from_value_text(component, parsed["value"].get("source_text"))
        component["values_by_denko_level"][parsed["denko_level"]] = parsed["value"]
    if components:
        out = sorted(components.values(), key=component_sort_key)
        inherit_supplemental_targets(out)
        add_component_health_reviews(out, values_by_denko_level, condition_context)
        return out

    fallback = normalize_skill_semantics(trigger_condition, effect_summary, activation_type, values_by_denko_level)
    return [
        {
            "component_id": f"component_{i + 1:02d}_{effect_kind}",
            "effect_kind": effect_kind,
            "target_scope": fallback.get("target_scope", []),
            "target_filters": {},
            "trigger_conditions": fallback.get("trigger", {}),
            "activation_type": activation_type,
            "condition_raw": trigger_condition or effect_summary,
            "remarks_raw": skill_remarks,
            "values_by_denko_level": {},
            "confidence": "low",
            "needs_review": True,
            "review_reasons": ["component_values_not_parsed"],
        }
        for i, effect_kind in enumerate(fallback.get("effect_kind", []))
    ]


def parse_level_components(common_text: str, row_fact: dict[str, Any]) -> list[dict[str, Any]]:
    raw_row = row_fact.get("raw_row") or {}
    effect_text = row_fact.get("effect") or ""
    text = " ".join(value for value in [common_text, row_fact.get("special_explanation"), effect_text] if value)
    components: list[dict[str, Any]] = []
    for seasonal_component in parse_seasonal_components(row_fact):
        components.append(seasonal_component)
    for weekday_component in parse_weekday_components(row_fact):
        components.append(weekday_component)

    number = r"[+＋-]?\d+(?:\.\d+)?"
    label_pattern = r"[\(（](\d+)[\)）]"
    stat_plain_number = r"[+＋-]?\d+(?:\.\d+)?(?![\d.]|\s*[×x])"
    stat_value_pattern = rf"{stat_plain_number}\s*[％%]?(?:\s*[～〜~\-]\s*(?:{stat_plain_number}|x)\s*[％%]?)?"
    formula_value_pattern = r"[+＋-]?(?:n|x|\d+(?:\.\d+)?)\s*[×x]\s*[^％%\s]+[％%]"
    for formula_match in re.finditer(rf"(?:{label_pattern}\s*)?(ATK|DEF)\s*({formula_value_pattern})", effect_text):
        label = f"({formula_match.group(1)})" if formula_match.group(1) else None
        stat = formula_match.group(2)
        value_text = normalize_numeric_text(f"{stat} {formula_match.group(3)}")
        signed_value = parse_signed_number(value_text)
        if "n" in value_text or "x" in value_text or "×" in value_text:
            signed_value = None
        kind = ("atk_debuff" if signed_value is not None and signed_value < 0 else "atk_buff") if stat == "ATK" else (
            "def_debuff" if signed_value is not None and signed_value < 0 else "def_buff"
        )
        append_component_once(
            components,
            component_value(
                kind,
                row_fact,
                value_text,
                signed_value,
                "formula_percent",
                condition_label=label,
                effect_role=effect_role_from_label(label, common_text),
            ),
        )
    for shared_match in re.finditer(rf"(?:{label_pattern}\s*)?ATK\s*(?:&|＆|/|・)\s*DEF\s*({stat_value_pattern})", effect_text):
        label = f"({shared_match.group(1)})" if shared_match.group(1) else None
        for stat, kind in [("ATK", "atk_buff"), ("DEF", "def_buff")]:
            value_text = normalize_numeric_text(f"{stat} {shared_match.group(2)}")
            append_component_once(
                components,
                component_value(
                    kind,
                    row_fact,
                    value_text,
                    parse_signed_number(value_text),
                    "percent_range" if is_range_text(value_text) else "percent",
                    condition_label=label,
                    effect_role=effect_role_from_label(label, common_text),
                ),
            )

    stat_matches = list(
        re.finditer(
            rf"(?:{label_pattern}\s*)?(ATK|DEF)\s*({stat_value_pattern})",
            effect_text,
        )
    )
    labels_for_order = labels_for_ordered_stat_values(effect_text, common_text)
    stat_seen: dict[str, int] = {}
    kind_seen: dict[str, int] = {}
    for match in stat_matches:
        stat = match.group(2)
        stat_seen[stat] = stat_seen.get(stat, 0) + 1
        value_text = normalize_numeric_text(f"{stat} {match.group(3)}")
        signed_value = parse_signed_number(value_text)
        if stat == "ATK":
            kind = "atk_debuff" if signed_value is not None and signed_value < 0 else "atk_buff"
        else:
            kind = "def_debuff" if signed_value is not None and signed_value < 0 else "def_buff"
        kind_seen[kind] = kind_seen.get(kind, 0) + 1
        label = f"({match.group(1)})" if match.group(1) else inferred_or_ordered_label(
            common_text,
            kind,
            kind_seen[kind],
            labels_for_order,
            stat_seen[stat],
            stat_matches,
            stat,
        )
        append_component_once(
            components,
            component_value(
                kind,
                row_fact,
                value_text,
                signed_value,
                "percent_range" if is_range_text(value_text) else "percent",
                condition_label=label,
                effect_role=effect_role_from_label(label, common_text),
            ),
        )

    for hp_match in re.finditer(rf"(?:{label_pattern}\s*)?HPの\s*(\d+)\s*[％%]", effect_text):
        label = f"({hp_match.group(1)})" if hp_match.group(1) else None
        components.append(
            component_value(
                "hp_recovery",
                row_fact,
                f"HPの{hp_match.group(2)}%",
                int(hp_match.group(2)),
                "percent_hp",
                condition_label=label,
                effect_role=effect_role_from_label(label, common_text),
            )
        )
    for hp_match in re.finditer(rf"(?:{label_pattern}\s*)?HP回復\s*({number})", effect_text):
        label = f"({hp_match.group(1)})" if hp_match.group(1) else None
        components.append(
            component_value(
                "hp_recovery",
                row_fact,
                normalize_numeric_text(f"HP回復 {hp_match.group(2)}"),
                parse_signed_number(hp_match.group(2)),
                "flat_hp",
                condition_label=label,
                effect_role=effect_role_from_label(label, common_text),
            )
        )

    radar_match = re.search(r"レーダー(?:最大検知数|範囲)\s*\+?\s*(\d+)", text)
    if radar_match:
        parsed = component_value(
            "radar_detection_range",
            row_fact,
            f"レーダー最大検知数 +{radar_match.group(1)}",
            int(radar_match.group(1)),
            "station_count",
        )
        parsed["target_scope"] = ["self"]
        parsed["trigger_conditions"] = {"item": "radar", "event_hint": "item_use"}
        append_component_once(components, parsed)

    if "これまでアクセスしたことのある駅" in text and "アクセス" in text:
        parsed = component_value(
            "random_previous_station_access",
            row_fact,
            "これまでアクセスしたことのある駅にアクセス",
            None,
            "boolean",
        )
        parsed["target_scope"] = ["self"]
        parsed["trigger_conditions"] = {
            "event_hint": "accessed",
            "access_direction": "received",
            "hp_outcome": "zero",
            "destination": "previously_accessed_station",
        }
        append_component_once(components, parsed)

    label_before_or_after = rf"(?:(?:{label_pattern}\s*)?(?P<name>{{name}})\s*(?:{label_pattern}\s*)?)"
    for kind, effect_name, unit in [
        ("exp_gain", "経験値付与", "flat_exp"),
        ("additional_fixed_damage", "追加固定ダメージ", "flat_damage"),
        ("fixed_damage", "(?<!追加)固定ダメージ", "flat_damage"),
        ("damage_reduction", "ダメージ軽減", "flat_damage"),
        ("film_series_effect_boost", "フィルムシリーズ効果の着用数", "count"),
    ]:
        value_token = rf"(?:{number}|x)(?:\s*[～〜~\-]\s*(?:{number}|x))?"
        effect_raw = effect_name.replace("(?<!追加)", "")
        grouped_pattern = re.compile(rf"{effect_name}\s*((?:{label_pattern}\s*{value_token}\s*)+)")
        for grouped in grouped_pattern.finditer(effect_text):
            for label_value in re.finditer(rf"{label_pattern}\s*({value_token})", grouped.group(1)):
                label = f"({label_value.group(1)})"
                value_number = label_value.group(2)
                value_raw = normalize_numeric_text(f"{effect_raw} {value_number}")
                append_component_once(
                    components,
                    component_value(
                        kind,
                        row_fact,
                        value_raw,
                        parse_signed_number(value_number),
                        f"{unit}_range" if is_range_text(value_number) else unit,
                        condition_label=label,
                        effect_role=effect_role_from_label(label, common_text),
                    ),
                )
        pattern = label_before_or_after.format(name=effect_name) + rf"\s*({value_token})"
        for match in re.finditer(pattern, effect_text):
            label_number = match.group(1) or match.group(3)
            label = f"({label_number})" if label_number else None
            value_number = match.group(4)
            value_raw = normalize_numeric_text(f"{effect_raw} {value_number}")
            append_component_once(
                components,
                component_value(
                    kind,
                    row_fact,
                    value_raw,
                    parse_signed_number(value_number),
                    f"{unit}_range" if is_range_text(value_number) else unit,
                    condition_label=label,
                    effect_role=effect_role_from_label(label, common_text),
                )
            )

    for exp_match in re.finditer(rf"(?:{label_pattern}\s*)?(?:相手に)?経験値\s*({number})", effect_text):
        label = f"({exp_match.group(1)})" if exp_match.group(1) else None
        value_raw = normalize_numeric_text(f"経験値 {exp_match.group(2)}")
        parsed = component_value(
            "exp_gain",
            row_fact,
            value_raw,
            parse_signed_number(exp_match.group(2)),
            "flat_exp",
            condition_label=label,
            effect_role=effect_role_from_label(label, common_text),
        )
        if "相手に" in exp_match.group(0):
            parsed["target_scope"] = ["opponent_denko"]
        append_component_once(components, parsed)

    damage_value_pattern = r"[+＋-]?\d+(?:\.\d+)?(?:\s*[×x]\s*n)?(?:\s*[～〜~\-]\s*[+＋-]?\d+(?:\.\d+)?)?"
    for damage_match in re.finditer(rf"(?:{label_pattern}\s*)?ダメージ\s*({damage_value_pattern})", effect_text):
        if "固定" in effect_text[max(0, damage_match.start() - 4) : damage_match.start()]:
            continue
        label = f"({damage_match.group(1)})" if damage_match.group(1) else None
        value_raw = normalize_numeric_text(f"ダメージ {damage_match.group(2)}")
        signed_value = parse_signed_number(value_raw)
        kind = "damage_reduction" if signed_value is not None and signed_value < 0 else "fixed_damage"
        parsed = component_value(
            kind,
            row_fact,
            value_raw,
            None if "n" in value_raw or "×" in value_raw or "x" in value_raw else signed_value,
            "formula_flat_damage" if "n" in value_raw or "×" in value_raw or "x" in value_raw else "flat_damage",
            condition_label=label,
            effect_role=effect_role_from_label(label, common_text),
        )
        append_component_once(components, parsed)

    for reference_delta_match in re.finditer(rf"{label_pattern}\s*\(1\)\s*([+＋]\d+(?:\.\d+)?)", effect_text):
        label = f"({reference_delta_match.group(1)})"
        segment = component_condition_text(common_text, {"condition_label": label})
        if "固定ダメージ" not in segment and "ダメージ" not in segment:
            continue
        value_raw = normalize_numeric_text(f"追加固定ダメージ (1){reference_delta_match.group(2)}")
        append_component_once(
            components,
            component_value(
                "additional_fixed_damage",
                row_fact,
                value_raw,
                parse_signed_number(reference_delta_match.group(2)),
                "flat_damage_delta",
                condition_label=label,
                effect_role=effect_role_from_label(label, common_text),
            ),
        )

    duration_pattern = re.compile(
        rf"(?:{label_pattern}\s*)?(?:(?:スキル)?効果時間\s*)?((?:バッテリー1個につき)?\s*[+＋]\d+(?:時間|分|秒)(?:\d+秒)?)"
    )
    for match in duration_pattern.finditer(effect_text):
        label = f"({match.group(1)})" if match.group(1) else None
        duration_raw = normalize_numeric_text(f"効果時間 {match.group(2).strip()}")
        components.append(
            component_value(
                "duration_extension",
                row_fact,
                duration_raw,
                parse_signed_number(duration_raw),
                "duration_delta",
                condition_label=label,
                effect_role=effect_role_from_label(label, common_text),
            )
        )

    bare_percent_pattern = re.compile(rf"^(?:{label_pattern}\s*)?\s*([+＋-]?\d+(?:\.\d+)?\s*[％%])\s*$")
    bare_percent_match = bare_percent_pattern.match(effect_text.strip())
    if bare_percent_match:
        label = f"({bare_percent_match.group(1)})" if bare_percent_match.group(1) else None
        inferred_kind = infer_effect_kind_for_bare_value(common_text, label)
        if inferred_kind:
            value_raw = normalize_numeric_text(bare_percent_match.group(2))
            append_component_once(
                components,
                component_value(
                    inferred_kind,
                    row_fact,
                    value_raw,
                    parse_signed_number(value_raw),
                    "percent",
                    condition_label=label,
                    effect_role=effect_role_from_label(label, common_text),
                ),
            )

    labeled_percent_pattern = re.compile(rf"{label_pattern}\s*([+＋-]?\d+(?:\.\d+)?\s*[％%])")
    labeled_percent_matches = list(labeled_percent_pattern.finditer(effect_text))
    if len(labeled_percent_matches) > 1:
        for percent_match in labeled_percent_matches:
            label = f"({percent_match.group(1)})"
            inferred_kind = infer_effect_kind_for_bare_value(common_text, label)
            if not inferred_kind:
                continue
            value_raw = normalize_numeric_text(percent_match.group(2))
            append_component_once(
                components,
                component_value(
                    inferred_kind,
                    row_fact,
                    value_raw,
                    parse_signed_number(value_raw),
                    "percent",
                    condition_label=label,
                    effect_role=effect_role_from_label(label, common_text),
                ),
            )

    score_value = rf"(?:[+＋]?\d+|x)(?:\s*[～〜~\-]\s*(?:[+＋]?\d+|x))?"
    score_pattern = re.compile(rf"(?:{label_pattern}\s*)?(?:合計ダメージが\s*(\d+)\s*→\s*)?スコア獲得\s*({score_value})(?:/駅)?")
    score_matches = list(score_pattern.finditer(effect_text))
    for index, match in enumerate(score_matches):
        label = f"({match.group(1)})" if match.group(1) else None
        kind = "score_gain" if (label == "(1)" or (not label and index == 0)) else "additional_score_gain"
        unit = "score_per_station" if "/駅" in match.group(0) else "score"
        parsed = component_value(
            kind,
            row_fact,
            normalize_numeric_text(f"スコア獲得 {match.group(3)}"),
            parse_signed_number(match.group(3)),
            "score_range" if is_range_text(match.group(3)) else unit,
            condition_label=label,
            effect_role=effect_role_from_label(label, common_text),
        )
        if match.group(2):
            parsed["value"]["score_trigger_threshold_raw"] = f"合計ダメージが{match.group(2)}"
            parsed["value"]["score_trigger_threshold_damage"] = int(match.group(2))
        components.append(parsed)

    access_match = re.search(r"追加アクセス\s*\+?\s*(\d+)回", text)
    if access_match:
        components.append(component_value("extra_access", row_fact, access_match.group(0), int(access_match.group(1)), "count"))
    elif "もう1度だけアクセス" in text:
        components.append(component_value("extra_access", row_fact, "もう1度だけアクセス", 1, "count"))

    if "フットバーすことがある" in text or "フットバーします" in text:
        components.append(component_value("footbar", row_fact, "相手をフットバーすことがある", None, "boolean"))

    if "スキル無効化" in text or "スキルを無効化" in text:
        components.append(component_value("skill_disable", row_fact, skill_disable_value_raw(text), None, "boolean"))

    station_count = raw_row.get("思い出しアクセス可能駅数")
    if station_count:
        components.append(component_value("memory_access_station_count", row_fact, station_count, parse_signed_number(station_count), "station_count"))
    memory_time = raw_row.get("思い出しアクセス可能時間")
    if memory_time:
        components.append(component_value("memory_access_time", row_fact, memory_time, None, "duration"))

    return components


def parse_seasonal_components(row_fact: dict[str, Any]) -> list[dict[str, Any]]:
    seasonal_values = row_fact.get("seasonal_values") or {}
    if not seasonal_values:
        return []
    specs = [
        ("seasonal_exp_gain_spring", "exp_gain", "経験値付与", "flat_exp", "3～5月", [3, 4, 5], ["accessing_denko"]),
        ("seasonal_fixed_damage_summer", "fixed_damage", "固定ダメージ", "flat_damage", "6～8月", [6, 7, 8], ["team_all"]),
        ("seasonal_score_gain_autumn", "score_gain", "スコア獲得", "score", "9～11月", [9, 10, 11], ["team_all"]),
        ("seasonal_damage_reduction_winter", "damage_reduction", "ダメージ軽減", "flat_damage", "12～2月", [12, 1, 2], ["team_all"]),
    ]
    out = []
    multiplier = seasonal_multiplier_raw(row_fact.get("effect") or "")
    for component_id, effect_kind, raw_name, unit, months_raw, months, target_scope in specs:
        value_number = seasonal_values.get(effect_kind)
        if not value_number:
            continue
        value_raw = f"{raw_name} {value_number}"
        if multiplier:
            value_raw = f"{value_raw} ※効果量 {multiplier}"
        parsed = component_value(
            effect_kind,
            row_fact,
            value_raw,
            parse_signed_number(value_number),
            unit,
        )
        parsed["component_id"] = component_id
        parsed["value"]["season_months_raw"] = months_raw
        parsed["value"]["season_months"] = months
        if multiplier:
            parsed["value"]["seasonal_multiplier_raw"] = multiplier
        parsed["target_scope"] = target_scope
        parsed["target_filters"] = {"season_months": months, "season_months_raw": months_raw}
        return_value_text = row_fact.get("special_explanation") or ""
        if effect_kind == "damage_reduction" and "アクセスされた" in return_value_text:
            parsed["trigger_conditions"] = {"event_hint": "accessed", "access_direction": "received"}
        out.append(parsed)
    return out


def seasonal_multiplier_raw(effect_text: str) -> str | None:
    match = re.search(r"効果量\s*([xｘX\d.]+倍)", effect_text)
    return match.group(1) if match else None


def parse_weekday_components(row_fact: dict[str, Any]) -> list[dict[str, Any]]:
    effect_text = row_fact.get("effect") or ""
    source_text = row_fact.get("special_explanation") or ""
    if "曜日に応じた" not in effect_text and "曜日に応じて" not in source_text:
        return []
    specs = [
        ("weekday_atk_sunday", "atk_buff", "日曜日", "ATK増加", "sunday"),
        ("weekday_def_monday", "def_buff", "月曜日", "DEF増加", "monday"),
        ("weekday_atk_tuesday", "atk_buff", "火曜日", "ATK増加", "tuesday"),
        ("weekday_def_tuesday", "def_buff", "火曜日", "DEF増加", "tuesday"),
        ("weekday_fixed_damage_wednesday", "fixed_damage", "水曜日", "追加固定ダメージ", "wednesday"),
        ("weekday_damage_reduction_thursday", "damage_reduction", "木曜日", "固定ダメージ軽減", "thursday"),
        ("weekday_score_gain_friday", "score_gain", "金曜日", "スコア獲得", "friday"),
        ("weekday_exp_gain_saturday", "exp_gain", "土曜日", "経験値獲得", "saturday"),
    ]
    out = []
    for component_id, effect_kind, day_raw, raw_name, weekday in specs:
        parsed = component_value(
            effect_kind,
            row_fact,
            f"曜日変化: {day_raw} {raw_name}",
            None,
            "weekday_variable",
        )
        parsed["component_id"] = component_id
        parsed["target_scope"] = ["team_all"]
        parsed["target_filters"] = {"weekday": weekday, "weekday_raw": day_raw}
        parsed["trigger_conditions"] = {"basis": "activation_weekday", "weekday_dependent": True}
        parsed["value"]["weekday_raw"] = day_raw
        parsed["value"]["weekday"] = weekday
        parsed["value"]["needs_value_table_review"] = True
        out.append(parsed)

    daytime = weekday_vu_addition(row_fact.get("duration") or "", r"昼：\s*([^ ]+)")
    if daytime:
        parsed = component_value("duration_extension", row_fact, f"昼：{daytime}", None, "time")
        parsed["component_id"] = "vu_daytime_duration_extension"
        parsed["target_scope"] = ["team_all"]
        parsed["target_filters"] = {"time_window": "daytime", "time_window_raw": "昼"}
        parsed["trigger_conditions"] = {"time_window_raw": "6:00～18:00"}
        parsed["availability"] = {"vu_only": True, "note": "VU生效"}
        out.append(parsed)
    nighttime = weekday_vu_addition(row_fact.get("effect") or "", r"夜：\s*([^ ]+)")
    if nighttime:
        parsed = component_value("effect_multiplier", row_fact, f"夜：{nighttime}", None, "multiplier")
        parsed["component_id"] = "vu_night_effect_multiplier"
        parsed["target_scope"] = ["team_all"]
        parsed["target_filters"] = {"time_window": "nighttime", "time_window_raw": "夜"}
        parsed["trigger_conditions"] = {"time_window_raw": "18:00～翌6:00"}
        parsed["availability"] = {"vu_only": True, "note": "VU生效"}
        out.append(parsed)
    return out


def weekday_vu_addition(text: str, pattern: str) -> str | None:
    if not text:
        return None
    match = re.search(pattern, text)
    return match.group(1).strip() if match else None


def append_component_once(components: list[dict[str, Any]], parsed: dict[str, Any]) -> None:
    value = parsed.get("value") or {}
    signature = (parsed.get("component_id"), value.get("value_raw"))
    for existing in components:
        existing_value = existing.get("value") or {}
        if (existing.get("component_id"), existing_value.get("value_raw")) == signature:
            return
    components.append(parsed)


def ordered_effect_labels(text: str) -> list[str]:
    return [f"({match.group(1)})" for match in re.finditer(r"[\(（](\d+)[\)）]", normalize_numeric_text(text))]


def labels_for_ordered_stat_values(effect_text: str, common_text: str) -> list[str]:
    effect_labels = ordered_effect_labels(effect_text)
    if effect_labels and effect_labels[0] == "(1)":
        return effect_labels
    return [label for label, _segment in labeled_condition_segments(common_text)]


def inferred_or_ordered_label(
    common_text: str,
    effect_kind: str,
    kind_index: int,
    labels_for_order: list[str],
    stat_index: int,
    stat_matches: list[Any],
    stat: str,
) -> str | None:
    kind_labels = labels_for_effect_kind_from_conditions(common_text, effect_kind)
    if kind_labels and kind_index <= len(kind_labels):
        return kind_labels[kind_index - 1]
    return ordered_label_for_stat(labels_for_order, stat_index, stat_matches, stat)


def labels_for_effect_kind_from_conditions(text: str, effect_kind: str) -> list[str]:
    out: list[str] = []
    for label, segment in labeled_condition_segments(text):
        if effect_kind_matches_segment(effect_kind, segment):
            out.append(label)
    return out


def effect_kind_matches_segment(effect_kind: str, segment: str) -> bool:
    if effect_kind == "atk_buff":
        return "ATK" in segment and ("増加" in segment or "上昇" in segment)
    if effect_kind == "def_buff":
        return "DEF" in segment and ("増加" in segment or "上昇" in segment)
    if effect_kind == "atk_debuff":
        return "ATK" in segment and ("減少" in segment or "低下" in segment)
    if effect_kind == "def_debuff":
        return "DEF" in segment and ("減少" in segment or "低下" in segment)
    return False


def ordered_label_for_stat(labels: list[str], stat_index: int, stat_matches: list[Any], stat: str) -> str | None:
    same_stat_count = sum(1 for match in stat_matches if match.group(2) == stat)
    if same_stat_count <= 1 and labels:
        return labels[0]
    if labels and stat_index <= len(labels):
        return labels[stat_index - 1]
    return None


def parse_probability_boost_components(
    common_text: str,
    values_by_denko_level: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    normalized_common_text = normalize_numeric_text(common_text)
    if "(2)" not in normalized_common_text:
        return []
    if not re.search(r"発動率(?:UP|アップ|増加|上昇)|発動率.*(?:UP|アップ|増加|上昇)", normalized_common_text):
        return []
    condition_label = infer_condition_label_for_effect(normalized_common_text, "activation_probability_boost")
    out = []
    for denko_level, row_fact in values_by_denko_level.items():
        probability = row_fact.get("probability") or {}
        boost_parts = []
        for value in probability.values():
            if "(2)" in normalize_numeric_text(value):
                boost_parts.append(value)
        if not boost_parts:
            continue
        raw = " ".join(boost_parts)
        boost_match = re.search(r"\(2\)\s*([+＋]\d+%[～~][+＋]?\d+%)", raw)
        out.append(
            {
                "component_id": "activation_probability_boost",
                "effect_kind": "activation_probability_boost",
                "condition_label": condition_label,
                "denko_level": denko_level,
                "value": {
                    "value_raw": raw,
                    "value_numeric": None,
                    "unit": "percent_range" if boost_match else "raw_probability_modifier",
                    "probability": probability,
                    "duration": row_fact.get("duration"),
                    "cooldown": row_fact.get("cooldown"),
                    "skill_level": row_fact.get("skill_level"),
                    "source_text": row_fact.get("special_explanation"),
                    "raw_row": row_fact.get("raw_row"),
                },
            }
        )
    return out


def enrich_component_from_value_text(component: dict[str, Any], source_text: str | None) -> None:
    if not source_text:
        return
    source_segment = relevant_source_segment(source_text, component.get("condition_raw") or "")
    source_target = infer_target_scope_from_source_text(source_segment, component.get("effect_kind") or "")
    if source_target and not component.get("target_scope"):
        component["target_scope"] = source_target
    target_scope = component.setdefault("target_scope", [])
    if "編成内" in source_segment and not target_scope:
        target_scope.append("team_all")
    filters = component.setdefault("target_filters", {})
    if "先頭の場合は2両目" in source_text:
        filters["position_exception_raw"] = "自身が先頭の場合は2両目"
    if "自身には効果がありません" in source_text or "自身には効果がない" in source_text:
        filters["exclude_self"] = True


def relevant_source_segment(source_text: str, condition_raw: str) -> str:
    if not condition_raw:
        return source_text
    clauses = [
        clause.strip()
        for clause in re.split(r"(?<=。)|また、|ただし、", source_text)
        if clause.strip()
    ]
    if not clauses:
        return source_text
    cue_words = [
        "今日のアクセス駅数",
        "アクセスした駅",
        "天気",
        "曇り",
        "リンク駅数",
        "最大HP",
        "AP",
        "バッテリー",
        "効果時間",
        "リブート",
        "固定ダメージ",
        "経験値",
    ]
    best_clause = clauses[0]
    best_score = -1
    for clause in clauses:
        score = 0
        for cue in cue_words:
            if cue in condition_raw and cue in clause:
                score += 2
        if component_label_text(condition_raw) in clause:
            score += 1
        if score > best_score:
            best_clause = clause
            best_score = score
    return best_clause if best_score > 0 else source_text


def component_label_text(condition_raw: str) -> str:
    match = re.search(r"[\(（](\d+)[\)）]", condition_raw)
    return f"({match.group(1)})" if match else ""


def infer_target_scope_from_source_text(text: str, effect_kind: str) -> list[str]:
    if "アクセスしたでんこに" in text:
        return ["accessing_denko"]
    if "アクセスしたでんこ" in text and effect_kind in {"exp_gain", "score_gain"}:
        return ["accessing_denko"]
    if "編成内のでんこに" in text or "編成内のでんこへ" in text:
        return ["team_all"]
    return []


def adjust_component_semantics(component: dict[str, Any], common_text: str) -> None:
    if component.get("effect_kind") == "fixed_damage" and (
        "追加固定ダメージ" in common_text or ("(2)" in common_text and "属性" in common_text)
    ):
        filters = component.setdefault("target_filters", {})
        filters.pop("attribute", None)


def component_value(
    effect_kind: str,
    row_fact: dict[str, Any],
    value_raw: str,
    value_numeric: int | None,
    unit: str,
    condition_label: str | None = None,
    effect_role: str | None = None,
) -> dict[str, Any]:
    component_id = f"{effect_kind}_{condition_label.strip('()')}" if condition_label else effect_kind
    value = {
        "value_raw": value_raw,
        "value_numeric": value_numeric,
        "unit": unit,
        "probability": probability_for_label(row_fact.get("probability") or {}, condition_label),
        "duration": row_fact.get("duration"),
        "cooldown": row_fact.get("cooldown"),
        "skill_level": row_fact.get("skill_level"),
        "source_text": row_fact.get("special_explanation"),
        "raw_row": row_fact.get("raw_row"),
    }
    value.update(range_value_fields(value_raw))
    return {
        "component_id": component_id,
        "effect_kind": effect_kind,
        "condition_label": condition_label,
        "effect_role": effect_role,
        "value": value,
    }


def parse_signed_number(value: str) -> int | None:
    match = re.search(r"([+＋-]?\d+(?:\.\d+)?)", value)
    if not match:
        return None
    text = match.group(1).replace("＋", "+")
    number = float(text)
    return int(number) if number.is_integer() else number


def normalize_numeric_text(value: str) -> str:
    return value.replace("＋", "+").replace("（", "(").replace("）", ")").strip()


def is_range_text(value: str) -> bool:
    return bool(re.search(r"[～〜~\-]\s*[+＋-]?\d+(?:\.\d+)?", value))


def range_value_fields(value: str) -> dict[str, Any]:
    if not is_range_text(value):
        return {}
    numbers = [float(match.group(0).replace("＋", "+")) for match in re.finditer(r"[+＋-]?\d+(?:\.\d+)?", value)]
    if len(numbers) < 2:
        return {}
    def clean(number: float) -> int | float:
        return int(number) if number.is_integer() else number
    return {"value_min": clean(numbers[0]), "value_max": clean(numbers[1])}


def probability_for_label(probability: dict[str, str], label: str | None) -> dict[str, str]:
    if not label or not probability:
        return probability
    out: dict[str, str] = {}
    label_number = label.strip("()")
    for key, value in probability.items():
        extracted = extract_labeled_probability(value, label_number)
        out[key] = extracted or value
    return out


def extract_labeled_probability(value: str, label_number: str) -> str | None:
    text = normalize_numeric_text(value)
    # Handles both "(1)75%" and combined labels like "(1)(2)100%".
    pattern = re.compile(r"((?:\(\d+\))+)\s*([+＋-]?\d+(?:\.\d+)?(?:\s*[～〜~\-]\s*[+＋-]?\d+(?:\.\d+)?)?\s*[％%])")
    for match in pattern.finditer(text):
        labels = re.findall(r"\((\d+)\)", match.group(1))
        if label_number in labels:
            return normalize_numeric_text(match.group(2))
    segment = extract_labeled_condition_text(text, f"({label_number})")
    percent_match = re.search(r"([+＋-]?\d+(?:\.\d+)?(?:\s*[～〜~\-]\s*[+＋-]?\d+(?:\.\d+)?)?\s*[％%])", segment)
    if percent_match:
        return normalize_numeric_text(percent_match.group(1))
    return None


def effect_role_from_label(label: str | None, condition_text: str) -> str | None:
    if label == "(1)":
        return "default_effect"
    if label:
        segment = extract_labeled_condition_text(condition_text, label)
        return "additional_effect" if "追加" in segment else "supplemental_effect"
    return None


def labeled_condition_segments(text: str) -> list[tuple[str, str]]:
    normalized = normalize_numeric_text(text)
    starts = []
    for match in re.finditer(r"\((\d+)\)", normalized):
        index = match.start()
        prev = normalized[:index].rstrip()
        next_text = normalized[match.end() :]
        next_char = next_text[:1]
        if not prev or prev.endswith("/") or prev.endswith("効果") or prev.endswith("効果:") or prev.endswith("効果："):
            starts.append((index, f"({match.group(1)})"))
            continue
        if normalized[index - 1].isspace() and next_char and next_char not in {"発"}:
            starts.append((index, f"({match.group(1)})"))
    out = []
    for pos, (start, label) in enumerate(starts):
        end = starts[pos + 1][0] if pos + 1 < len(starts) else len(normalized)
        segment = normalized[start:end].strip(" /")
        segment = re.sub(r"\s*効果\s*$", "", segment).strip()
        out.append((label, segment))
    return out


def extract_labeled_condition_text(text: str, label: str | None) -> str:
    if not label:
        return ""
    for segment_label, segment in labeled_condition_segments(text):
        if segment_label == label:
            return segment
    return ""


def component_condition_text(common_text: str, parsed: dict[str, Any]) -> str:
    labeled = extract_labeled_condition_text(common_text, parsed.get("condition_label"))
    prefix = condition_prefix_before_labels(common_text)
    if labeled and prefix:
        return f"{prefix} {labeled}"
    return labeled or common_text


def component_sort_key(component: dict[str, Any]) -> tuple[int, str]:
    label = component.get("condition_label")
    if label:
        match = re.search(r"\d+", label)
        if match:
            return (int(match.group(0)), component.get("component_id") or "")
    return (999, component.get("component_id") or "")


def add_condition_only_components(
    components: dict[str, dict[str, Any]],
    condition_text: str,
    activation_type: str | None,
    values_by_denko_level: dict[str, dict[str, Any]],
) -> None:
    for label, segment in labeled_condition_segments(condition_text):
        label_number = label.strip("()")
        if any(component.get("condition_label") == label for component in components.values()):
            continue
        effect_kind = condition_only_effect_kind(segment)
        if not effect_kind:
            continue
        component_id = f"{effect_kind}_{label_number}"
        component = {
            "component_id": component_id,
            "effect_kind": effect_kind,
            "effect_role": effect_role_from_label(label, condition_text),
            "condition_label": label,
            "target_scope": infer_target_scope(segment, effect_kind),
            "target_filters": infer_target_filters(segment, effect_kind),
            "trigger_conditions": infer_trigger_conditions(segment, effect_kind),
            "scaling_conditions": infer_scaling_conditions(segment),
            "activation_type": activation_type,
            "condition_raw": component_condition_text(condition_text, {"condition_label": label}),
            "remarks_raw": None,
            "values_by_denko_level": {},
            "confidence": "low",
            "needs_review": True,
            "review_reasons": ["condition_only_component_needs_review"],
        }
        for denko_level, row_fact in values_by_denko_level.items():
            component["values_by_denko_level"][denko_level] = {
                "value_raw": effect_kind,
                "value_numeric": None,
                "unit": "condition_only",
                "probability": probability_for_label(row_fact.get("probability") or {}, label),
                "duration": row_fact.get("duration"),
                "cooldown": row_fact.get("cooldown"),
                "skill_level": row_fact.get("skill_level"),
                "source_text": row_fact.get("special_explanation"),
                "raw_row": row_fact.get("raw_row"),
            }
        components[component_id] = component


def drop_unlabeled_duplicates_when_labeled_exists(components: dict[str, dict[str, Any]]) -> None:
    labeled_kinds = {
        component.get("effect_kind")
        for component in components.values()
        if component.get("condition_label")
    }
    for component_id, component in list(components.items()):
        if component.get("condition_label"):
            continue
        if component.get("effect_kind") in labeled_kinds and re.search(r"[\(（]\d+[\)）]", component.get("condition_raw") or ""):
            del components[component_id]


def condition_only_effect_kind(segment: str) -> str | None:
    if "スキル無効化" in segment or "スキルを無効化" in segment:
        return "skill_disable"
    if "効果時間延長" in segment or ("効果時間" in segment and "延長" in segment):
        return "duration_extension"
    if "クールタイムに入らず" in segment or "スキルを継続" in segment or "スキル継続率" in segment:
        return "skill_continue"
    if "リブート" in segment:
        return "reboot"
    if "バッテリー使用不可" in segment:
        return "battery_disable"
    return None


def condition_prefix_before_labels(text: str) -> str:
    normalized = normalize_numeric_text(text)
    segments = labeled_condition_segments(normalized)
    if not segments:
        return ""
    first = normalized.find(segments[0][1])
    prefix = normalized[:first].strip(" /")
    return re.sub(r"(?:効果|効果[:：])\s*$", "", prefix).strip()


def infer_condition_label_for_effect(text: str, effect_kind: str) -> str | None:
    keyword_by_kind = {
        "atk_buff": "ATK",
        "atk_debuff": "ATK",
        "def_buff": "DEF",
        "def_debuff": "DEF",
        "fixed_damage": "固定ダメージ",
        "additional_fixed_damage": "追加固定ダメージ",
        "damage_reduction": "ダメージ軽減",
        "exp_gain": "経験値",
        "duration_extension": "効果時間",
        "activation_probability_boost": "発動率",
        "skill_disable": "スキル無効化",
    }
    keyword = keyword_by_kind.get(effect_kind)
    if not keyword:
        return None
    for label in re.findall(r"[\(（](\d+)[\)）]", text):
        segment = extract_labeled_condition_text(text, f"({label})")
        if keyword in segment:
            return f"({label})"
    return None


def infer_effect_kind_for_bare_value(text: str, label: str | None) -> str | None:
    segment = component_condition_text(text, {"condition_label": label}) if label else text
    if "効果時間" in segment or "スキル発動時間" in segment:
        return "duration_extension"
    if "経験値" in segment:
        return "exp_gain"
    if "スコア" in segment:
        return "score_gain"
    if "ATK" in segment:
        return "atk_buff"
    if "DEF" in segment:
        return "def_buff"
    return None


def add_component_health_reviews(
    components: list[dict[str, Any]],
    values_by_denko_level: dict[str, dict[str, Any]],
    condition_text: str,
) -> None:
    source_levels = set(values_by_denko_level.keys())
    expected_labels = {label.strip("()") for label, _segment in labeled_condition_segments(condition_text)}
    emitted_labels = {
        str(component.get("condition_label")).strip("()")
        for component in components
        if component.get("condition_label")
    }
    label_mismatch = expected_labels and not expected_labels.issubset(emitted_labels)
    duplicate_signatures = set() if "重複" in condition_text else component_duplicate_signatures(components)
    for component in components:
        reasons = component.setdefault("review_reasons", [])
        values = component.get("values_by_denko_level") or {}
        vu_only = component_has_only_vu_values(component)
        annotate_component_availability(component, vu_only)
        if is_primary_labeled_component(component) and vu_only and (
            "primary_labeled_effect_vu_only_needs_review" not in reasons
        ):
            reasons.append("primary_labeled_effect_vu_only_needs_review")
        if label_declared_vu_only(component, condition_text) and not vu_only and (
            "vu_label_level_mismatch_needs_review" not in reasons
        ):
            reasons.append("vu_label_level_mismatch_needs_review")
        if not vu_only and "30" in source_levels and "30" not in values and "key_level_component_missing" not in reasons:
            reasons.append("key_level_component_missing")
        if not vu_only and "50" in source_levels and "50" not in values and "key_level_component_missing" not in reasons:
            reasons.append("key_level_component_missing")
        if label_mismatch and "labeled_component_count_mismatch" not in reasons:
            reasons.append("labeled_component_count_mismatch")
        if label_mismatch and re.search(r"[\(（]\d+[\)）][\(（]\d+[\)）]", condition_text) and (
            "compound_labeled_effect_needs_manual_review" not in reasons
        ):
            reasons.append("compound_labeled_effect_needs_manual_review")
        if component.get("component_id") in duplicate_signatures and (
            "duplicate_labeled_component_values_need_review" not in reasons
        ):
            reasons.append("duplicate_labeled_component_values_need_review")
        if has_condition_effect_mismatch(component) and "condition_effect_mismatch_needs_review" not in reasons:
            reasons.append("condition_effect_mismatch_needs_review")
        if has_attribute_branch_condition(component) and "attribute_branch_effect_needs_review" not in reasons:
            reasons.append("attribute_branch_effect_needs_review")


def inherit_supplemental_targets(components: list[dict[str, Any]]) -> None:
    last_by_kind: dict[str, dict[str, Any]] = {}
    by_kind_and_label: dict[tuple[str, str], dict[str, Any]] = {}
    for component in components:
        effect_kind = component.get("effect_kind") or ""
        condition_raw = component.get("condition_raw") or ""
        condition_label = component.get("condition_label") or ""
        referenced_labels = [
            f"({label})"
            for label in re.findall(r"[\(（](\d+)[\)）]", condition_raw)
            if f"({label})" != condition_label
        ]
        if component.get("effect_role") in {"supplemental_effect", "additional_effect"} and "追加" in condition_raw:
            previous = last_by_kind.get(effect_kind)
            if previous and not has_explicit_target_phrase(condition_raw):
                component["target_scope"] = list(previous.get("target_scope") or [])
                inherited_filters = dict(previous.get("target_filters") or {})
                inherited_filters.update(component.get("target_filters") or {})
                component["target_filters"] = inherited_filters
        elif component.get("effect_role") in {"supplemental_effect", "additional_effect"} and referenced_labels:
            for referenced_label in referenced_labels:
                previous = by_kind_and_label.get((effect_kind, referenced_label))
                if previous and not has_explicit_target_phrase(condition_raw):
                    component["target_scope"] = list(previous.get("target_scope") or [])
                    inherited_filters = dict(previous.get("target_filters") or {})
                    inherited_filters.update(component.get("target_filters") or {})
                    component["target_filters"] = inherited_filters
                    break
        last_by_kind[effect_kind] = component
        if condition_label:
            by_kind_and_label[(effect_kind, condition_label)] = component


def has_explicit_target_phrase(text: str) -> bool:
    return any(
        phrase in text
        for phrase in [
            "アクセスしたでんこに",
            "自身以外",
            "自身の1両前",
            "先頭車両",
            "編成内の全てのでんこ",
            "編成内のでんこのATK",
            "編成内のでんこのDEF",
        ]
    )


def has_condition_effect_mismatch(component: dict[str, Any]) -> bool:
    text = component.get("condition_raw") or ""
    effect_kind = component.get("effect_kind") or ""
    if effect_kind == "activation_probability_boost" and "発動率" in text:
        return False
    if effect_kind == "duration_extension" and "効果時間" in text:
        return False
    if effect_kind == "fixed_damage" and ("固定ダメージ" in text or "軽減不能なダメージ" in text):
        return False
    if effect_kind == "exp_gain" and "経験値" in text:
        return False
    if effect_kind in {"hp_recovery", "def_debuff", "atk_debuff"} and (
        "HP回復" in text or "HPを回復" in text
    ):
        return effect_kind != "hp_recovery"
    if ("経験値" in text or "スコア" in text) and effect_kind not in {"exp_gain", "score_gain", "additional_score_gain"}:
        return True
    if "リブート" in text and effect_kind != "reboot" and "しなかった" not in text:
        return True
    return False


def has_attribute_branch_condition(component: dict[str, Any]) -> bool:
    text = component.get("condition_raw") or ""
    attrs = [attr for attr in ["heat", "cool", "eco", "flat"] if attr in text]
    return "なら" in text and len(attrs) >= 2


def annotate_component_availability(component: dict[str, Any], vu_only: bool | None = None) -> None:
    values = component.get("values_by_denko_level") or {}
    levels = sorted(values.keys(), key=lambda level: int(level) if str(level).isdigit() else 999)
    availability = component.setdefault("availability", {})
    availability["levels"] = levels
    availability["vu_only"] = component_has_only_vu_values(component) if vu_only is None else vu_only
    if availability["vu_only"]:
        availability["note"] = "VU生效"


def component_duplicate_signatures(components: list[dict[str, Any]]) -> set[str]:
    by_signature: dict[tuple[Any, ...], list[str]] = {}
    for component in components:
        values = component.get("values_by_denko_level") or {}
        signature = (
            component.get("effect_kind"),
            tuple(
                sorted(
                    (
                        level,
                        value.get("value_raw"),
                        json.dumps(value.get("probability") or {}, ensure_ascii=False, sort_keys=True),
                    )
                    for level, value in values.items()
                )
            ),
        )
        by_signature.setdefault(signature, []).append(component.get("component_id") or "")
    out = set()
    for ids in by_signature.values():
        if len(ids) > 1:
            out.update(ids)
    return out


def component_has_only_vu_values(component: dict[str, Any]) -> bool:
    levels = set((component.get("values_by_denko_level") or {}).keys())
    return bool(levels) and levels.issubset(set(VU_LEVELS))


def is_primary_labeled_component(component: dict[str, Any]) -> bool:
    label = component.get("condition_label")
    if label and str(label).strip() in {"(1)", "（1）"}:
        return True
    component_id = str(component.get("component_id") or "")
    return bool(re.search(r"(?:^|_)1(?:_|$)", component_id))


def label_declared_vu_only(component: dict[str, Any], text: str) -> bool:
    label = component.get("condition_label")
    if not label:
        return False
    label_number = str(label).strip("()")
    normalized = normalize_numeric_text(text)
    return bool(re.search(rf"\({re.escape(label_number)}\)\s*は\s*Lv\.?\s*92\s*以降", normalized))


def join_unique_text(values: list[str | None]) -> str:
    out: list[str] = []
    for value in values:
        value = clean_condition_text(value)
        if value and value not in out:
            out.append(value)
    return " ".join(out)


def clean_condition_text(value: str | None) -> str | None:
    if not value:
        return value
    out = value
    for first in ["heat", "cool", "eco", "flat"]:
        for second in ["heat", "cool", "eco", "flat"]:
            if first == second:
                continue
            out = out.replace(
                f"と の両属性のでんこのみ編成 {first} {second}",
                f"{first}と{second}の両属性のでんこのみ編成",
            )
            out = out.replace(
                f"発動条件： と のみ編成 {first} {second}",
                f"発動条件：{first}と{second}のみ編成",
            )
            out = out.replace(
                f"と のみ編成 {first} {second}",
                f"{first}と{second}のみ編成",
            )
    return out


def infer_scaling_conditions(text: str) -> dict[str, Any]:
    scaling: dict[str, Any] = {}
    if "最も長いリンク時間" in text and "リンク時間の合計" in text:
        scaling["basis"] = "team_each_denko_max_link_time_sum"
    if "同じテーマのフィルム" in text or "同種のラッピング" in text:
        scaling["basis"] = "same_theme_film_wearer_count"
    if "最大与ダメージ" in text:
        scaling["basis"] = "max_damage_dealt_during_skill"
    if "発動回数" in text:
        scaling["basis"] = "activation_count"
    if "リンク駅数" in text:
        scaling["basis"] = "linked_station_count"
    if "リンクしているでんこ" in text:
        scaling["basis"] = "linked_denko_count"
    cap_match = re.search(r"上限\s*(\d+)\s*体", text)
    if cap_match:
        scaling["max_count"] = int(cap_match.group(1))
    if "上限値はスキルLv.で異なる" in text:
        scaling["cap_varies_by_skill_level"] = True
    return scaling


def skill_disable_value_raw(text: str) -> str:
    for attr in ["heat", "cool", "eco", "flat"]:
        if attr in text:
            return f"{attr}属性でんこのスキル無効化"
    return "スキル無効化"


def infer_target_scope(text: str, effect_kind: str) -> list[str]:
    if "相手" in text and effect_kind in {"exp_gain", "hp_recovery", "def_debuff", "atk_debuff", "fixed_damage", "damage_reduction"}:
        return ["opponent_denko"]
    if any(phrase in text for phrase in ["自分以外", "自身以外", "自身を除く"]) and effect_kind in {
        "atk_buff",
        "def_buff",
        "exp_gain",
        "score_gain",
        "damage_reduction",
    }:
        return ["team_all"]
    if effect_kind in {"exp_gain", "score_gain"} and any(phrase in text for phrase in ["ほかのでんこ", "他のでんこ"]):
        return ["team_all"]
    if "自身のATK" in text or "自身のDEF" in text or "自分のATK" in text or "自分のDEF" in text:
        return ["self"]
    if "自身の1両前のでんこ" in text or "1両前のでんこ" in text:
        return ["relative_car"]
    if "自身以外" in text:
        return ["team_all"]
    if "先頭車両" in text or "先頭から1両目" in text:
        return ["front_car"]
    if "アクセスしたでんこに" in text:
        return ["accessing_denko"]
    if "相手と自身の編成内" in text:
        return ["opponent_team", "own_team"]
    if "編成内の全てのでんこ" in text or "編成内でんこ" in text or "編成内のでんこ" in text or "編成内" in text:
        return ["team_all"]
    if effect_kind in {"atk_debuff", "def_debuff"} and "相手" in text:
        return ["opponent_denko"]
    if "メロ自身" in text or "自身" in text:
        return ["self"]
    if effect_kind in {"atk_buff", "def_buff", "fixed_damage", "score_gain", "exp_gain", "damage_reduction"}:
        return ["self"]
    if effect_kind in {"memory_access_station_count", "memory_access_time"}:
        return ["team_all"]
    return []


def infer_target_filters(text: str, effect_kind: str) -> dict[str, Any]:
    filters: dict[str, Any] = {}
    attrs = [attr for attr in ["heat", "cool", "eco", "flat"] if f"{attr}属性" in text or attr in text]
    name_filter = infer_name_filter(text)
    if name_filter:
        filters["name_contains_any"] = name_filter
        filters["script"] = "hiragana_or_katakana"
    if len(attrs) > 1:
        filters["attributes"] = attrs
        if "のみ編成" in text or "のみの編成" in text:
            filters["formation_only"] = True
    if "自身を除く" in text:
        filters["exclude_self"] = True
    if "自身以外" in text:
        filters["exclude_self"] = True
    if "自分以外" in text:
        filters["exclude_self"] = True
    if "自身には効果がありません" in text or "自身には効果がない" in text:
        filters["exclude_self"] = True
    if "自身の1両前のでんこ" in text or "1両前のでんこ" in text:
        filters["relative_position"] = "one_car_before_self"
    if "自身を除く先頭から1両目" in text:
        filters["position_exception_raw"] = "自身が先頭の場合は2両目"
    if "2両目" in text and ("先頭" in text or "先頭車両" in text):
        filters["position_exception_raw"] = "自身が先頭の場合は2両目"
    attr_match = re.search(r"(heat|cool|eco|flat)属性", text)
    if attr_match and "attributes" not in filters:
        if "相手のでんこ" in text or text.startswith("相手") or "相手編成" in text:
            filters["opponent_attribute"] = attr_match.group(1)
        else:
            filters["attribute"] = attr_match.group(1)
    opponent_count = re.search(r"相手編成に\s*(\d+)\s*体以上\s*(heat|cool|eco|flat)属性", text)
    if opponent_count:
        filters["opponent_team_attribute_min_count"] = {
            "attribute": opponent_count.group(2),
            "min_count": int(opponent_count.group(1)),
        }
    opponent_count_alt = re.search(r"相手編成内\s*(heat|cool|eco|flat)属性でんこ数が\s*(\d+)\s*体以上", text)
    if opponent_count_alt:
        filters["opponent_team_attribute_min_count"] = {
            "attribute": opponent_count_alt.group(1),
            "min_count": int(opponent_count_alt.group(2)),
        }
    if "相手編成内のでんこの属性の数" in text:
        filters["opponent_team_attribute_count_basis"] = "distinct_attribute_count"
    own_count = re.search(r"編成内に\s*(heat|cool|eco|flat)属性のでんこが\s*(\d+)\s*体以上", text)
    if own_count:
        filters["own_team_attribute_min_count"] = {
            "attribute": own_count.group(1),
            "min_count": int(own_count.group(2)),
        }
    opponent_all = re.search(r"相手の編成が全て\s*(heat|cool|eco|flat)", text)
    if opponent_all:
        filters["opponent_team_all_attribute"] = opponent_all.group(1)
    own_all = re.search(r"全て\s*(heat|cool|eco|flat)属性編成", text)
    if own_all:
        filters["own_team_all_attribute"] = own_all.group(1)
    formation_size = re.search(r"(\d+)両編成以上", text)
    if formation_size:
        filters["formation_size_min"] = int(formation_size.group(1))
    active_skill_count = re.search(r"編成内の「いつでもアクティブ」.*?数が\s*(\d+)\s*体以上", text)
    if active_skill_count:
        filters["own_team_skill_activation_mode_min_count"] = {
            "activation_type": "いつでもアクティブ",
            "min_count": int(active_skill_count.group(1)),
        }
    type_map = {
        "アタッカー": "attacker",
        "ディフェンダー": "defender",
        "サポーター": "supporter",
        "トリックスター": "trickster",
    }
    for raw_type, normalized_type in type_map.items():
        if raw_type in text:
            filters["type"] = normalized_type
            break
    if effect_kind == "skill_disable":
        filters["disabled_skill_target"] = skill_disable_value_raw(text)
    return filters


def infer_name_filter(text: str) -> list[str]:
    if "名前に" not in text:
        return []
    quoted = re.search(r"「([^」]+)」のいずれか", text)
    if quoted:
        return list(quoted.group(1))
    quoted = re.search(r"「([^」]+)」", text)
    if quoted:
        return [quoted.group(1)]
    return []


def infer_trigger_conditions(text: str, effect_kind: str | None = None) -> dict[str, Any]:
    trigger: dict[str, Any] = {}
    hp_threshold = re.search(r"HPが(\d+)%以下", text)
    if hp_threshold:
        trigger["hp_threshold_percent"] = int(hp_threshold.group(1))
        trigger["operator"] = "lte"
    if "被アクセス" in text or "アクセスされた" in text:
        trigger["event_hint"] = "accessed"
        trigger["access_direction"] = "received"
    elif "アクセス" in text:
        trigger["event_hint"] = "access"
        trigger["access_direction"] = "active"
    if "リンクした" in text:
        trigger["event_hint"] = "link"
        trigger["access_direction"] = "own_team_link"
    if "自身がリンクしている" in text:
        trigger["station_ownership"] = "self_linking"
    if "バッテリー使用" in text or "バッテリー1個につき" in text:
        trigger["event_hint"] = "battery_use"
        trigger["per_battery_use"] = True
    if effect_kind == "activation_probability_boost" and "いつでもアクティブ" in text and "でんこ数" in text:
        trigger["active_skill_holder_count_based"] = True
    time_match = re.search(r"(\d{1,2}:\d{2}[～\-]\d{1,2}:\d{2})", text)
    if time_match:
        trigger["time_window_raw"] = time_match.group(1)
    return trigger


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
        "available_denko_levels": sorted(values_by_denko_level.keys(), key=level_sort_key),
    }


def level_sort_key(level: str) -> tuple[int, int]:
    if level == "base":
        return (0, 0)
    if level.isdigit():
        return (1, int(level))
    return (2, 0)


def build_summary_zh(
    skill_components: list[dict[str, Any]] | None,
    normalized_skill: dict[str, Any] | None,
    lv50: dict[str, Any] | None,
    values_by_denko_level: dict[str, dict[str, Any]] | None,
) -> str | None:
    if skill_components:
        return "；".join(component_summary_zh(i + 1, component) for i, component in enumerate(skill_components))
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
        "accessing_denko": "访问したでんこ",
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


def component_summary_zh(index: int, component: dict[str, Any]) -> str:
    effect_labels = {
        "atk_buff": "ATK增加",
        "def_buff": "DEF增加",
        "hp_recovery": "HP回复",
        "footbar": "フットバー",
        "extra_access": "追加访问",
        "skill_disable": "技能无效化",
        "exp_gain": "经验值获得",
        "fixed_damage": "固定伤害",
        "damage_reduction": "伤害减轻",
        "memory_access_station_count": "思い出しアクセス駅数",
        "memory_access_time": "思い出しアクセス时间",
    }
    target_labels = {
        "team_all": "编成内全员",
        "front_car": "先头车",
        "self": "自身",
        "accessing_denko": "访问したでんこ",
        "own_team": "自己编成",
        "opponent_team": "对方编成",
    }
    values = component.get("values_by_denko_level") or {}
    preferred_level = "50" if "50" in values else ("base" if "base" in values else next(iter(values), None))
    value_text = ""
    if preferred_level:
        value = values[preferred_level]
        value_text = compact_component_value_zh(preferred_level, value)
    targets = "、".join(target_labels.get(target, target) for target in component.get("target_scope", []))
    prefix = f"技能分量{index}：{effect_labels.get(component.get('effect_kind'), component.get('effect_kind'))}"
    if targets:
        prefix += f" / 对象：{targets}"
    if value_text:
        prefix += f" / {value_text}"
    return prefix


def compact_component_value_zh(level: str, value: dict[str, Any]) -> str:
    parts = [f"Lv{level}" if level != "base" else "基础"]
    if value.get("value_raw"):
        parts.append(value["value_raw"])
    probability = value.get("probability") or {}
    if probability:
        parts.append("，".join(f"{key} {item}" for key, item in probability.items()))
    if value.get("duration"):
        parts.append(value["duration"])
    if value.get("cooldown"):
        parts.append(f"CD {value['cooldown']}")
    return "，".join(parts)


def skill_level_cell(values: dict[str, dict[str, Any]], lv: str) -> str:
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
            value = clean_condition_text(row.get(key))
            if value and value not in values:
                values.append(value)
    return " / ".join(values) if values else None


def extract_key_level_stats(record: dict[str, Any]) -> dict[str, dict[str, str]]:
    target_levels = set(KEY_DENKO_LEVELS)
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
        "  <title>Denko Ingestion Probe Report</title>",
        "  <style>",
        "    body { font-family: system-ui, sans-serif; line-height: 1.5; margin: 24px; }",
        "    table { border-collapse: collapse; width: 100%; margin: 12px 0 24px; }",
        "    th, td { border: 1px solid #ccc; padding: 6px 8px; vertical-align: top; }",
        "    th { background: #f5f5f5; }",
        "    code { background: #f6f8fa; padding: 1px 4px; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <h1>Denko Ingestion Probe Report</h1>",
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
    lines.append("  <h2>技能分量</h2>")
    lines.append("  <table>")
    lines.append("    <thead><tr><th>denko_id</th><th>name</th><th>component</th><th>effect</th><th>target</th><th>filters</th><th>Lv30</th><th>Lv50/base</th><th>Lv60</th><th>VU 92/96/100</th><th>conditions</th></tr></thead>")
    lines.append("    <tbody>")
    for skill in skill_rows:
        for component in skill.get("skill_components", []) or []:
            values = component.get("values_by_denko_level") or {}
            lv30 = values.get("30") or {}
            lv50_or_base = values.get("50") or values.get("base") or {}
            lv60 = values.get("60") or {}
            vu_values = []
            for lv in VU_LEVELS:
                if values.get(lv):
                    vu_values.append(compact_component_value_zh(lv, values[lv]))
            lines.append(
                "      <tr>"
                f"<td>{esc(skill['denko_id'])}</td>"
                f"<td>{esc(skill['name'])}</td>"
                f"<td>{esc(component.get('component_id'))}</td>"
                f"<td>{esc(component.get('effect_kind'))}</td>"
                f"<td>{esc(', '.join(component.get('target_scope') or []))}</td>"
                f"<td>{esc(json.dumps(component.get('target_filters') or {}, ensure_ascii=False))}</td>"
                f"<td>{esc(compact_component_value_zh('30', lv30) if lv30 else '')}</td>"
                f"<td>{esc(compact_component_value_zh('50' if values.get('50') else 'base', lv50_or_base) if lv50_or_base else '')}</td>"
                f"<td>{esc(compact_component_value_zh('60', lv60) if lv60 else '')}</td>"
                f"<td>{esc(' / '.join(vu_values))}</td>"
                f"<td>{esc(json.dumps(component.get('trigger_conditions') or {}, ensure_ascii=False))}</td>"
                "</tr>"
            )
    lines.append("    </tbody>")
    lines.append("  </table>")
    lines.append("  <h2>技能等级值</h2>")
    for pool in ("original", "extra"):
        lines.append(f"  <h3>{esc(pool)}</h3>")
        lines.append("  <table>")
        skill_headers = "".join(f"<th>Lv{level}</th>" for level in KEY_DENKO_LEVELS)
        lines.append(f"    <thead><tr><th>denko_id</th><th>name</th>{skill_headers}</tr></thead>")
        lines.append("    <tbody>")
        for skill in [s for s in skill_rows if s["pool"] == pool]:
            values = skill.get("values_by_denko_level", {})
            skill_cells = "".join(f"<td>{esc(skill_level_cell(values, level))}</td>" for level in KEY_DENKO_LEVELS)
            lines.append(
                "      <tr>"
                f"<td>{esc(skill['denko_id'])}</td>"
                f"<td>{esc(skill['name'])}</td>"
                f"{skill_cells}"
                "</tr>"
            )
        lines.append("    </tbody>")
        lines.append("  </table>")
    lines.append("  <h2>关键 AP/HP 节点</h2>")
    for pool in ("original", "extra"):
        lines.append(f"  <h3>{esc(pool)}</h3>")
        lines.append("  <table>")
        stat_headers = "".join(f"<th>Lv{level}</th>" for level in KEY_DENKO_LEVELS)
        lines.append(f"    <thead><tr><th>denko_id</th><th>name</th>{stat_headers}</tr></thead>")
        lines.append("    <tbody>")
        for skill in [s for s in skill_rows if s["pool"] == pool]:
            nodes = skill.get("key_level_stats", {})
            def cell(lv: str) -> str:
                node = nodes.get(lv)
                return f"AP {node.get('AP')} / HP {node.get('HP')}" if node else ""
            stat_cells = "".join(f"<td>{esc(cell(level))}</td>" for level in KEY_DENKO_LEVELS)
            lines.append(
                "      <tr>"
                f"<td>{esc(skill['denko_id'])}</td>"
                f"<td>{esc(skill['name'])}</td>"
                f"{stat_cells}"
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
            "    <li><code>data/records/probe_first5_denko_facts.jsonl</code></li>",
            "    <li><code>data/records/probe_first5_skill_facts.jsonl</code></li>",
            "    <li><code>data/indexes/probe_first5_denko_index.json</code></li>",
            "    <li><code>data/review_queue/probe_first5_review_queue.jsonl</code></li>",
            "    <li><code>data/reports/probe_first5_report_zh.html</code></li>",
            "  </ul>",
            "</body>",
            "</html>",
        ]
    )
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "probe_first5_report_zh.html").write_text("\n".join(lines), encoding="utf-8")


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
    write_jsonl(RECORD_DIR / "probe_first5_denko_facts.jsonl", all_records)
    write_jsonl(RECORD_DIR / "probe_first5_skill_facts.jsonl", skill_rows)
    write_jsonl(REVIEW_DIR / "probe_first5_review_queue.jsonl", all_reviews)
    (INDEX_DIR / "probe_first5_denko_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    write_report(all_records, skill_rows, all_reviews)
    print(json.dumps({"denko_records": len(all_records), "skill_records": len(skill_rows), "reviews": len(all_reviews)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
