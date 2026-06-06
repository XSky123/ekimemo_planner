from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag


ROOT = Path(__file__).resolve().parents[2]
RAW_PATH = ROOT / "data" / "raw_pages" / "skill_reverse_lookup.html"
RECORD_DIR = ROOT / "data" / "records"
REPORT_DIR = ROOT / "data" / "reports"
BASE_URL = "https://newekimemo.wiki.fc2.com"
SOURCE_URL = "https://newekimemo.wiki.fc2.com/wiki/%E3%81%A7%E3%82%93%E3%81%93%E3%82%B9%E3%82%AD%E3%83%AB%E9%80%86%E5%BC%95%E3%81%8D%E8%A1%A8"
JST = timezone(timedelta(hours=9))
PARSER_VERSION = "reverse_skill_lookup.bs4.v1"


def normalize_text(value: str) -> str:
    value = html.unescape(value).replace("\xa0", " ")
    value = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", value).strip()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def int_attr(cell: Tag, name: str, default: int = 1) -> int:
    try:
        return max(1, int(cell.get(name, default)))
    except (TypeError, ValueError):
        return default


def expand_table(table: Tag) -> list[list[dict[str, Any]]]:
    matrix: list[list[dict[str, Any]]] = []
    spans: dict[int, tuple[int, dict[str, Any]]] = {}
    rows = table.find_all("tr")
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
        for cell_node in row.find_all(["td", "th"], recursive=False):
            fill_spans()
            rowspan = int_attr(cell_node, "rowspan")
            colspan = int_attr(cell_node, "colspan")
            cell = {
                "text": normalize_text(cell_node.get_text(" ", strip=True)),
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


def headers_and_rows(matrix: list[list[dict[str, Any]]]) -> tuple[list[str], list[list[dict[str, Any]]]]:
    if not matrix:
        return [], []
    first = [cell["text"] for cell in matrix[0]]
    if len(matrix) > 1:
        second = [cell["text"] for cell in matrix[1]]
        if any(text in second for text in ["編成位置", "タイプ", "属性"]):
            headers = []
            for i, text in enumerate(second):
                if text in ["編成位置", "タイプ", "属性"]:
                    headers.append(text)
                else:
                    headers.append(first[i] if i < len(first) and first[i] != text else text)
            return headers, matrix[2:]
    return first, matrix[1:]


def parse_denko_entries(cell: Tag) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    contents = list(cell.contents)
    for index, child in enumerate(contents):
        if not isinstance(child, Tag) or child.name != "a":
            continue
        prev_text = ""
        if index > 0 and isinstance(contents[index - 1], NavigableString):
            prev_text = str(contents[index - 1])
        suffix_parts = []
        for following in contents[index + 1 :]:
            if isinstance(following, Tag) and following.name == "a":
                break
            suffix_parts.append(following.get_text(" ", strip=True) if isinstance(following, Tag) else str(following))
        suffix = normalize_text("".join(suffix_parts))
        leading_segment = re.split(r"[、,]", suffix, maxsplit=1)[0]
        condition_hint = normalize_text(leading_segment.strip(" 、"))
        markers = "".join(mark for mark in ["※", "▲"] if mark in prev_text)
        entries.append(
            {
                "name": normalize_text(child.get_text(" ", strip=True)),
                "wiki_page_title": child.get("title"),
                "detail_url": urljoin(BASE_URL, child.get("href", "")),
                "marker_raw": markers or None,
                "has_team_attribute_condition_marker": "※" in markers,
                "has_external_condition_marker": "▲" in markers,
                "condition_hint_raw": condition_hint if condition_hint.startswith(("(", "（")) else None,
            }
        )
    return entries


def row_dict(headers: list[str], row: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {headers[i]: row[i] for i in range(min(len(headers), len(row)))}


def parse_reverse_lookup(html_text: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html_text, "html.parser")
    content_hash = sha256_text(html_text)
    records: list[dict[str, Any]] = []
    current_category = None
    current_target_section = None
    current_effect_group = None
    table_index = -1

    for element in soup.find_all(["h3", "h4", "span", "table"]):
        if element.name == "h3":
            current_category = normalize_text(element.get_text(" ", strip=True))
            current_target_section = None
            current_effect_group = None
            continue
        if element.name == "h4":
            current_target_section = normalize_text(element.get_text(" ", strip=True))
            current_effect_group = None
            continue
        if element.name == "span":
            text = normalize_text(element.get_text(" ", strip=True))
            if re.fullmatch(r"[（(].+[）)]", text):
                current_effect_group = text.strip("()（）")
            continue
        if element.name != "table":
            continue

        table_index += 1
        matrix = expand_table(element)
        headers, rows = headers_and_rows(matrix)
        if "でんこ" not in headers:
            continue
        for row_index, row in enumerate(rows):
            cells = row_dict(headers, row)
            denko_cell = cells.get("でんこ", {}).get("node")
            if not denko_cell:
                continue
            for denko in parse_denko_entries(denko_cell):
                effect_raw = cells.get("効果", {}).get("text") or current_effect_group
                record = {
                    "record_meta": {
                        "source_url": SOURCE_URL,
                        "source_authority": "reverse_lookup_prior",
                        "content_hash": content_hash,
                        "parser_version": PARSER_VERSION,
                        "parsed_at": datetime.now(JST).isoformat(),
                        "confidence": "medium",
                        "needs_review": True,
                        "review_reasons": ["reverse_lookup_is_candidate_source", "detail_page_required_for_values"],
                    },
                    "lookup_category": current_category,
                    "target_section": current_target_section,
                    "effect_group": current_effect_group,
                    "effect_raw": effect_raw,
                    "target_position_raw": cells.get("編成位置", {}).get("text") or cells.get("対象でんこ", {}).get("text"),
                    "target_type_raw": cells.get("タイプ", {}).get("text"),
                    "target_attribute_raw": cells.get("属性", {}).get("text"),
                    "condition_raw": cells.get("条件", {}).get("text"),
                    "pool_raw": cells.get("種類", {}).get("text"),
                    "denko_name": denko["name"],
                    "wiki_page_title": denko["wiki_page_title"],
                    "detail_url": denko["detail_url"],
                    "marker_raw": denko["marker_raw"],
                    "has_team_attribute_condition_marker": denko["has_team_attribute_condition_marker"],
                    "has_external_condition_marker": denko["has_external_condition_marker"],
                    "condition_hint_raw": denko["condition_hint_raw"],
                    "source_table_index": table_index,
                    "source_row_index": row_index,
                }
                records.append(record)
    return records


def write_report(records: list[dict[str, Any]]) -> None:
    def esc(value: Any) -> str:
        return html.escape("" if value is None else str(value))

    atk_team = [
        row
        for row in records
        if row.get("lookup_category") == "攻撃系スキル"
        and row.get("effect_raw") == "ATK増加"
        and row.get("target_section") == "対象:編成内"
        and row.get("target_position_raw") == "編成内全員"
        and row.get("target_type_raw") == "全タイプ"
        and row.get("target_attribute_raw") == "全属性"
    ]
    lines = [
        "<!doctype html>",
        '<html lang="zh-CN">',
        "<head><meta charset=\"utf-8\"><title>Reverse Skill Lookup Sample</title>",
        "<style>body{font-family:system-ui,sans-serif;line-height:1.5;margin:24px}table{border-collapse:collapse;width:100%;margin:12px 0 24px}th,td{border:1px solid #ccc;padding:6px 8px;vertical-align:top}th{background:#f5f5f5}</style>",
        "</head><body>",
        "<h1>技能反查表样本</h1>",
        "<p>本报告把 wiki 反查表解析成“候选生成矩阵”。数值、持续时间、CD 仍需详情页确认。</p>",
        f"<p>解析候选总数：{len(records)}；全队 ATK 增加样本：{len(atk_team)}。</p>",
        "<h2>全队 ATK 增加候选</h2>",
        "<table><thead><tr><th>denko</th><th>pool</th><th>effect</th><th>target</th><th>type</th><th>attribute</th><th>marker</th><th>condition hint</th><th>detail</th></tr></thead><tbody>",
    ]
    for row in atk_team:
        lines.append(
            "<tr>"
            f"<td>{esc(row['denko_name'])}</td>"
            f"<td>{esc(row['pool_raw'])}</td>"
            f"<td>{esc(row['effect_raw'])}</td>"
            f"<td>{esc(row['target_position_raw'])}</td>"
            f"<td>{esc(row['target_type_raw'])}</td>"
            f"<td>{esc(row['target_attribute_raw'])}</td>"
            f"<td>{esc(row['marker_raw'])}</td>"
            f"<td>{esc(row['condition_hint_raw'])}</td>"
            f"<td>{esc(row['detail_url'])}</td>"
            "</tr>"
        )
    lines.extend(["</tbody></table>", "</body></html>"])
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "reverse_skill_lookup_sample_zh.html").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    html_text = RAW_PATH.read_text(encoding="utf-8", errors="replace")
    records = parse_reverse_lookup(html_text)
    RECORD_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RECORD_DIR / "reverse_skill_lookup_candidates.jsonl"
    out_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in records),
        encoding="utf-8",
    )
    write_report(records)
    print(json.dumps({"reverse_lookup_candidates": len(records)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
