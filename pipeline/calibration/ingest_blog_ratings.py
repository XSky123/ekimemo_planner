from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/reference_priors/blog_character_ratings.json"
DENKO = ROOT / "data/step1_db/denko_facts.jsonl"
SOURCES = {
    "attacker": "https://3secondsgameover.com/e/ekimemo_attacker",
    "defender": "https://3secondsgameover.com/e/ekimemo_defender",
    "supporter": "https://3secondsgameover.com/e/ekimemo_supporter",
    "trickster": "https://3secondsgameover.com/e/ekimemo_trickster",
}


def denko_id(label: str) -> str:
    number = int(re.search(r"(\d+)", label).group(1))
    return f"{'extra' if label.startswith('EX') else 'original'}:{number:03d}"


def name_index() -> dict[str, str]:
    rows = [json.loads(line) for line in DENKO.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = {}
    for row in rows:
        identity = row.get("identity") or {}
        denko = str(identity.get("denko_id") or row.get("denko_id"))
        for key in ("name", "full_name", "wiki_page_title"):
            if identity.get(key):
                result[str(identity[key])] = denko
    return result


def clean_comment(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" ・\n")
    stop_tokens = ("・元ネタ：", "・誕生日：", "・属性：", "・タイプ：", "・スキル：")
    for token in stop_tokens:
        index = value.find(token)
        if 0 <= index < 80:
            value = value[index + len(token):]
    return value[:700].strip()


def parse_page(kind: str, url: str, names: dict[str, str]) -> tuple[list[dict], dict]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 Step3 calibration audit"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
    soup = BeautifulSoup(payload, "html.parser")
    for node in soup(["script", "style", "noscript"]):
        node.decompose()
    text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))
    pattern = re.compile(
        r"(?P<label>(?:EX\s*)?No\.\s*\d+)\s+(?P<name>[^\s（(]+).*?"
        r"・オススメ度：\s*(?P<stars>[★☆✩]+)\s*(?P<comment>.*?)"
        r"(?=(?:EX\s*)?No\.\s*\d+\s+|関連記事|$)",
        re.S,
    )
    rows = []
    for match in pattern.finditer(text):
        stars = match.group("stars")
        name = match.group("name")
        rows.append({
            "denko_id": names.get(name) or denko_id(match.group("label")), "label": match.group("label"),
            "name_ja": match.group("name"), "type_page": kind,
            "rating": stars.count("★"), "rating_display": stars,
            "comment_ja": clean_comment(match.group("comment")), "source_url": url,
        })
    return rows, {"type_page": kind, "url": url, "content_hash": hashlib.sha256(payload).hexdigest(), "parsed_rows": len(rows)}


def main() -> int:
    ratings = []
    sources = []
    names = name_index()
    for kind, url in SOURCES.items():
        rows, source = parse_page(kind, url, names)
        ratings.extend(rows)
        sources.append(source)
    by_id = {row["denko_id"]: row for row in ratings}
    result = {
        "artifact": "blog_character_ratings", "version": "blog_character_ratings.v1",
        "source_authority": "recommendation_prior", "updated_through": "2025-05-07",
        "sources": sources, "counts": {"ratings": len(by_id)},
        "ratings": [by_id[key] for key in sorted(by_id)],
        "caveat_zh": "博客已于2025-05-07停止更新，只用于评价方法和玩家可用性对照，不覆盖Wiki详情事实。",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"ratings": len(by_id), "sources": sources}, ensure_ascii=False))
    return 0 if all(source["parsed_rows"] > 0 for source in sources) else 1


if __name__ == "__main__":
    raise SystemExit(main())
