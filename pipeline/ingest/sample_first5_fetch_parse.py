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
        meta = source_meta(
            detail.get("source_url") or ident.get("detail_url"),
            detail.get("detail_hash"),
            "detail_page",
            "low",
        )
        meta["review_reasons"] = [
            "sample_detail_probe_only",
            "full_skill_fact_not_extracted",
        ]
        rows.append(
            {
                "record_meta": meta,
                "denko_id": ident["denko_id"],
                "name": ident["name"],
                "pool": ident["pool"],
                "skill_name": record.get("list_page_fields", {}).get("skill_name"),
                "detail_url": ident.get("detail_url"),
                "skill_table_candidates": detail.get("skill_like_tables", []),
                "note_zh": "样本阶段只探测详情页技能相关表格，尚未确认完整 skill_fact。",
            }
        )
    return rows


def build_skill_review_items(skill_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reviews: list[dict[str, Any]] = []
    for row in skill_rows:
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
                "reason": "sample probe did not fully extract trigger/target/effect/values yet",
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
        lines.append("    <thead><tr><th>denko_id</th><th>wiki_no</th><th>name</th><th>type</th><th>attribute</th><th>color</th><th>skill_name</th><th>VU</th><th>detail tables</th><th>detail rowspan/colspan</th></tr></thead>")
        lines.append("    <tbody>")
        for record in [r for r in records if r["identity"]["pool"] == pool]:
            ident = record["identity"]
            fields = record["list_page_fields"]
            detail = record.get("detail_page_probe", {})
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
                f"<td>{esc(detail.get('table_count', ''))}</td>"
                f"<td>{esc(detail.get('rowspan_count', ''))}/{esc(detail.get('colspan_count', ''))}</td>"
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
            "    <li>详情页探测记录了 table 数量、rowspan/colspan 数量和技能相关表格摘要；这一步只做证据探测，不把未复核字段当最终技能事实。</li>",
            f"    <li>skill_fact 样本条目数：{len(skill_rows)}，全部标记为 low confidence / needs_review，因为尚未完整抽取 trigger、target、effect、values。</li>",
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
