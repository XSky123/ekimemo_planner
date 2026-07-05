from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, Tag


ROOT = Path(__file__).resolve().parents[2]
DENKO_FACTS = ROOT / "data" / "step1_db" / "denko_facts.jsonl"
CACHE_DIR = ROOT / "cache" / "prototype_pages"
REFERENCE_CACHE_DIR = ROOT / "cache" / "prototype_reference_pages"
STATE_PATH = ROOT / "cache" / "prototype_extract" / "state.json"
OUT_DIR = ROOT / "data" / "prototype_db"
OUT_JSONL = OUT_DIR / "sample_prototype_records.jsonl"
OUT_INDEX_JSON = OUT_DIR / "sample_prototype_index.json"
OUT_HTML = ROOT / "data" / "reports" / "step2_prototype_lookup_sample_zh.html"
FULL_OUT_JSONL = OUT_DIR / "prototype_records.jsonl"
FULL_OUT_INDEX_JSON = OUT_DIR / "prototype_index.json"
FULL_OUT_HTML = ROOT / "data" / "reports" / "step2_prototype_lookup_zh.html"

SAMPLE_IDS = [f"original:{idx:03d}" for idx in range(1, 6)] + [f"extra:{idx:03d}" for idx in range(1, 6)]
REFERENCE_PAGES = [
    {
        "cache_name": "ref_1.html",
        "source_kind": "homecoming_station_10th",
        "label": "返乡活动（10周年）",
        "priority": 100,
        "url": "https://ek1mem0.wiki.fc2.com/wiki/%E3%81%A7%E3%82%93%E3%81%93%E3%81%A8%E5%85%A8%E5%9B%BD%E5%90%84%E5%9C%B0%E3%81%AE%E9%A7%85%E3%81%AB%E3%81%8A%E3%81%A7%E3%81%8B%E3%81%91%E3%81%97%E3%82%88%E3%81%86%20%EF%BD%9E10%E5%91%A8%E5%B9%B4ver.%EF%BD%9E",
    },
    {
        "cache_name": "ref_2.html",
        "source_kind": "homecoming_station_original",
        "label": "返乡活动",
        "priority": 90,
        "url": "https://newekimemo.wiki.fc2.com/wiki/%E3%81%A7%E3%82%93%E3%81%93%E3%81%A8%E5%85%A8%E5%9B%BD%E5%90%84%E5%9C%B0%E3%81%AE%E9%A7%85%E3%81%AB%E3%81%8A%E3%81%A7%E3%81%8B%E3%81%91%E3%81%97%E3%82%88%E3%81%86",
    },
    {
        "cache_name": "ref_3.html",
        "source_kind": "prefecture_list",
        "label": "都道府県別一览",
        "priority": 70,
        "url": "https://newekimemo.wiki.fc2.com/wiki/%E3%81%A7%E3%82%93%E3%81%93%E4%B8%80%E8%A6%A7%2F%E9%83%BD%E9%81%93%E5%BA%9C%E7%9C%8C%E5%88%A5",
    },
]
BIRTHDAY_PROFILE_PAGE = {
    "cache_name": "birthday_profile.html",
    "source_kind": "birthday_profile",
    "label": "生日・プロフィール一览",
    "priority": 110,
    "url": "https://newekimemo.wiki.fc2.com/wiki/%E3%81%A7%E3%82%93%E3%81%93%E4%B8%80%E8%A6%A7%2F%E8%AA%95%E7%94%9F%E6%97%A5%E3%83%BB%E3%83%97%E3%83%AD%E3%83%95%E3%82%A3%E3%83%BC%E3%83%AB",
}
PROFILE_LABELS = ["タイプ", "属性", "でんこカラー", "誕生日", "声の担当", "キャラクターデザイン", "モデル車両・列車", "モデル車両"]
SECTION_STOP_WORDS = ["セリフ", "スキル", "ステータス詳細", "ラッピング", "名前について", "その他"]

PREFECTURE_READINGS = {
    "北海道": "ほっかいどう",
    "青森県": "あおもりけん",
    "岩手県": "いわてけん",
    "宮城県": "みやぎけん",
    "秋田県": "あきたけん",
    "山形県": "やまがたけん",
    "福島県": "ふくしまけん",
    "茨城県": "いばらきけん",
    "栃木県": "とちぎけん",
    "群馬県": "ぐんまけん",
    "埼玉県": "さいたまけん",
    "千葉県": "ちばけん",
    "東京都": "とうきょうと",
    "神奈川県": "かながわけん",
    "新潟県": "にいがたけん",
    "富山県": "とやまけん",
    "石川県": "いしかわけん",
    "福井県": "ふくいけん",
    "山梨県": "やまなしけん",
    "長野県": "ながのけん",
    "岐阜県": "ぎふけん",
    "静岡県": "しずおかけん",
    "愛知県": "あいちけん",
    "三重県": "みえけん",
    "滋賀県": "しがけん",
    "京都府": "きょうとふ",
    "大阪府": "おおさかふ",
    "兵庫県": "ひょうごけん",
    "奈良県": "ならけん",
    "和歌山県": "わかやまけん",
    "鳥取県": "とっとりけん",
    "島根県": "しまねけん",
    "岡山県": "おかやまけん",
    "広島県": "ひろしまけん",
    "山口県": "やまぐちけん",
    "徳島県": "とくしまけん",
    "香川県": "かがわけん",
    "愛媛県": "えひめけん",
    "高知県": "こうちけん",
    "福岡県": "ふくおかけん",
    "佐賀県": "さがけん",
    "長崎県": "ながさきけん",
    "熊本県": "くまもとけん",
    "大分県": "おおいたけん",
    "宮崎県": "みやざきけん",
    "鹿児島県": "かごしまけん",
    "沖縄県": "おきなわけん",
}

OPERATOR_READINGS = {
    "JR北海道": "じぇいあーるほっかいどう",
    "JR東日本": "じぇいあーるひがしにほん",
    "JR東海": "じぇいあーるとうかい",
    "JR西日本": "じぇいあーるにしにほん",
    "JR四国": "じぇいあーるしこく",
    "JR九州": "じぇいあーるきゅうしゅう",
    "JR貨物": "じぇいあーるかもつ",
    "国鉄": "こくてつ",
    "青い森鉄道": "あおいもりてつどう",
    "IGRいわて銀河鉄道": "あいじーあーるいわてぎんがてつどう",
    "三陸鉄道": "さんりくてつどう",
    "秋田内陸縦貫鉄道": "あきたないりくじゅうかんてつどう",
    "由利高原鉄道": "ゆりこうげんてつどう",
    "山形鉄道": "やまがたてつどう",
    "阿武隈急行": "あぶくまきゅうこう",
    "ひたちなか海浜鉄道": "ひたちなかかいひんてつどう",
    "小湊鉄道": "こみなとてつどう",
    "いすみ鉄道": "いすみてつどう",
    "京成電鉄": "けいせいでんてつ",
    "東急電鉄": "とうきゅうでんてつ",
    "小田急電鉄": "おだきゅうでんてつ",
    "江ノ島電鉄": "えのしまでんてつ",
    "小田急箱根鉄道": "おだきゅうはこねてつどう",
    "伊豆箱根鉄道": "いずはこねてつどう",
    "富士山麓電気鉄道": "ふじさんろくでんきてつどう",
    "しなの鉄道": "しなのてつどう",
    "えちごトキめき鉄道": "えちごときめきてつどう",
    "あいの風とやま鉄道": "あいのかぜとやまてつどう",
    "IRいしかわ鉄道": "あいあーるいしかわてつどう",
    "のと鉄道": "のとてつどう",
    "えちぜん鉄道": "えちぜんてつどう",
    "福井鉄道": "ふくいてつどう",
    "樽見鉄道": "たるみてつどう",
    "長良川鉄道": "ながらがわてつどう",
    "三岐鉄道": "さんぎてつどう",
    "近畿日本鉄道": "きんきにっぽんてつどう",
    "近江鉄道": "おうみてつどう",
    "信楽高原鐵道": "しがらきこうげんてつどう",
    "嵯峨野観光鉄道": "さがのかんこうてつどう",
    "京都丹後鉄道": "きょうとたんごてつどう",
    "南海電鉄": "なんかいでんてつ",
    "山陽電鉄": "さんようでんてつ",
    "広島電鉄": "ひろしまでんてつ",
    "一畑電気鉄道": "いちばたでんきてつどう",
    "土佐くろしお鉄道": "とさくろしおてつどう",
    "松浦鉄道": "まつうらてつどう",
    "島原鉄道": "しまばらてつどう",
    "南阿蘇鉄道": "みなみあそてつどう",
    "くま川鉄道": "くまがわてつどう",
    "ゆいレール": "ゆいれーる",
}

STATION_READINGS = {
    "五反田駅": "ごたんだえき",
    "東京貨物ターミナル駅": "とうきょうかもつたーみなるえき",
    "王子駅": "おうじえき",
    "八潮駅": "やしおえき",
    "新百合ヶ丘駅": "しんゆりがおかえき",
    "京橋駅": "きょうばしえき",
    "阿佐ヶ谷駅": "あさがやえき",
    "品川駅": "しながわえき",
    "上野駅": "うえのえき",
    "恋し浜駅": "こいしはまえき",
    "新利府駅": "しんりふえき",
    "八雲駅": "やくもえき",
    "為栗駅": "してぐりえき",
    "金城ふ頭駅": "きんじょうふとうえき",
    "新大阪駅": "しんおおさかえき",
    "福井駅": "ふくいえき",
    "福井駅駅": "ふくいえき",
    "田原町駅": "たわらまちえき",
    "倶利伽羅駅": "くりからえき",
    "高岡駅": "たかおかえき",
    "北府駅": "きたごえき",
    "勝山駅": "かつやまえき",
    "七尾駅": "ななおえき",
    "小浜駅": "おばまえき",
    "賢島駅": "かしこじまえき",
    "本宿駅": "もとじゅくえき",
    "蓮台寺駅": "れんだいじえき",
    "阿下喜駅": "あげきえき",
    "美濃白鳥駅": "みのしろとりえき",
    "新居浜駅": "にいはまえき",
    "坂出駅": "さかいでえき",
    "窪川駅": "くぼかわえき",
    "南郷駅": "なんごうえき",
    "首里駅": "しゅりえき",
    "花畑駅": "はなばたけえき",
    "サイアム駅": "さいあむえき",
    "Bellevue駅": "べるびゅーえき",
    "ソチミルコ駅": "そちみるこえき",
    "タスケーニャ駅": "たすけーにゃえき",
    "パリ北駅": "ぱりきたえき",
    "ニューデリー駅": "にゅーでりーえき",
}

VOICE_ACTOR_READINGS = {
    "ブリドカットセーラ恵美": "ぶりどかっとせーらえみ",
    "三上枝織": "みかみしおり",
    "中村カンナ": "なかむらかんな",
    "伊藤ゆいな": "いとうゆいな",
    "会沢紗弥": "あいざわさや",
    "佐々木未来": "ささきみこい",
    "内田秀": "うちだしゅう",
    "前田佳織里": "まえだかおり",
    "吉武千颯": "よしたけちはや",
    "和泉風花": "いずみふうか",
    "坂倉花": "さかくらさくら",
    "大坪由佳": "おおつぼゆか",
    "富田美憂": "とみたみゆ",
    "小岩井ことり": "こいわいことり",
    "小泉萌香": "こいずみもえか",
    "山本彩乃": "やまもとあやの",
    "山田麻莉奈": "やまだまりな",
    "徳井青空": "とくいそら",
    "日向未南": "ひなたみなみ",
    "星守紗凪": "ほしもりさな",
    "月城日花": "つきしろひな",
    "松井恵理子": "まついえりこ",
    "林鼓子": "はやしここ",
    "柳原かなこ": "やなぎはらかなこ",
    "水野朔": "みずのさく",
    "汐入あすか": "しおいりあすか",
    "河実里夏": "かわみりか",
    "田中ちえ美": "たなかちえみ",
    "田村佳奈": "たむらかな",
    "白城なお": "しらきなお",
    "直田姫奈": "すぐたひな",
    "礒部花凜": "いそべかりん",
    "立花理香": "たちばなりか",
    "紡木吏佐": "つむぎりさ",
    "船戸ゆり絵": "ふなとゆりえ",
    "花守ゆみり": "はなもりゆみり",
    "茅野愛衣": "かやのあい",
    "荒井麻那": "あらいまな",
    "荻野葉月": "おぎのはづき",
    "西本りみ": "にしもとりみ",
    "赤尾ひかる": "あかおひかる",
    "進藤あまね": "しんどうあまね",
    "鈴代紗弓": "すずしろさゆみ",
    "長江里加": "ながえりか",
    "関根明良": "せきねあきら",
    "陽高真白": "ひだかましろ",
    "青山なぎさ": "あおやまなぎさ",
    "香里有佐": "こうりありさ",
    "鳴沢優海": "なるさわゆうみ",
    "黒木ほの香": "くろきほのか",
    "野中ここな": "のなかここな",
}

FOREIGN_REGION_PREFIXES = {
    "アメリカ",
    "イギリス",
    "インド",
    "エジプト",
    "オランダ",
    "スイス",
    "タイ",
    "トルコ",
    "ドイツ",
    "ニュージーランド",
    "フランス",
    "ベトナム",
    "メキシコ",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat()


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows) + "\n", encoding="utf-8")


def cache_path_for(denko_id: str, url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    safe_id = denko_id.replace(":", "_")
    return CACHE_DIR / f"{safe_id}_{digest}.html"


def fetch_html(denko_id: str, url: str, state: dict[str, Any], refresh: bool = False) -> tuple[str, dict[str, Any]]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path_for(denko_id, url)
    fetched = False
    if refresh or not path.exists():
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 prototype-sample-parser/0.1"})
        with urlopen(request, timeout=25) as response:
            content = response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")
        path.write_text(content, encoding="utf-8")
        fetched = True
        time.sleep(0.25)
    html_text = path.read_text(encoding="utf-8")
    content_hash = hashlib.sha256(html_text.encode("utf-8")).hexdigest()
    state[denko_id] = {
        "cache_path": str(path.relative_to(ROOT)),
        "content_hash": content_hash,
        "detail_url": url,
        "fetched": fetched,
        "status": "cached" if not fetched else "fetched",
        "updated_at": now_iso(),
    }
    return html_text, state[denko_id]


def compact_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    text = re.sub(r"\s+([、。，．・）」』])", r"\1", text)
    text = re.sub(r"([（「『])\s+", r"\1", text)
    text = re.sub(r"\s+([）])", r"\1", text)
    text = re.sub(r"\s*・\s*", "・", text)
    text = re.sub(r"\s+(と兼任)(?=）)", r"\1", text)
    text = re.sub(r"(線|新幹線)\s+の", r"\1の", text)
    return text


def node_text(node: Tag) -> str:
    for br in node.find_all("br"):
        br.replace_with(" ")
    return compact_text(node.get_text(" ", strip=True))


def find_heading(soup: BeautifulSoup, text: str) -> Tag | None:
    return soup.find(lambda tag: tag.name in {"h2", "h3", "h4"} and text in tag.get_text(" ", strip=True))


def extract_section_text(soup: BeautifulSoup, heading_text: str, max_chars: int = 1800) -> str | None:
    heading = find_heading(soup, heading_text)
    if not heading:
        return None
    parts: list[str] = []
    current = heading
    while True:
        current = current.find_next_sibling()
        if current is None:
            break
        if isinstance(current, Tag) and current.name in {"h2", "h3"}:
            break
        if not isinstance(current, Tag):
            continue
        text = node_text(current)
        if not text:
            continue
        if heading_text == "プロフィール" and any(text.startswith(word) for word in SECTION_STOP_WORDS):
            break
        parts.append(text)
        if sum(len(part) for part in parts) >= max_chars:
            break
    if not parts:
        return None
    return compact_text(" ".join(parts))[:max_chars]


def profile_field(profile_text: str | None, label: str) -> str | None:
    if not profile_text:
        return None
    label_pattern = "|".join(re.escape(item) for item in PROFILE_LABELS)
    match = re.search(rf"{re.escape(label)}\s+(.+?)(?=\s+(?:{label_pattern})\s+|$)", profile_text)
    if not match:
        return None
    return compact_text(match.group(1))


def unique_keep_order(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        cleaned = compact_text(item).strip("「」『』、。 ")
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def unique_by_key(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        value = str(item.get(key) or "")
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(item)
    return result


def table_to_grid(table: Tag) -> list[list[str]]:
    grid: list[list[str]] = []
    rowspans: dict[int, tuple[int, str]] = {}
    for tr in table.find_all("tr"):
        row: list[str] = []
        col = 0
        cells = tr.find_all(["th", "td"], recursive=False)
        for cell in cells:
            while col in rowspans:
                remaining, text = rowspans[col]
                row.append(text)
                if remaining <= 1:
                    del rowspans[col]
                else:
                    rowspans[col] = (remaining - 1, text)
                col += 1
            text = node_text(cell)
            rowspan = int(cell.get("rowspan", 1) or 1)
            colspan = int(cell.get("colspan", 1) or 1)
            for _ in range(colspan):
                row.append(text)
                if rowspan > 1:
                    rowspans[col] = (rowspan - 1, text)
                col += 1
        while col in rowspans:
            remaining, text = rowspans[col]
            row.append(text)
            if remaining <= 1:
                del rowspans[col]
            else:
                rowspans[col] = (remaining - 1, text)
            col += 1
        if any(cell for cell in row):
            grid.append(row)
    return grid


def clean_reference_name(value: str) -> str:
    value = re.sub(r"\s*※\d+\s*", "", value)
    value = re.sub(r"\s*\(\*\d+\)\s*", "", value)
    return compact_text(value)


def build_denko_name_resolver(known_names: set[str]) -> dict[str, str]:
    aliases: dict[str, str] = {}
    collisions: set[str] = set()
    for name in known_names:
        aliases[name] = name
        for prefix in re.split(r"[・＝=]", name)[:1]:
            if prefix and prefix != name:
                if prefix in aliases and aliases[prefix] != name:
                    collisions.add(prefix)
                else:
                    aliases[prefix] = name
        for suffix_len in range(2, min(5, len(name)) + 1):
            suffix = name[-suffix_len:]
            if suffix in aliases and aliases[suffix] != name:
                collisions.add(suffix)
            else:
                aliases[suffix] = name
    for suffix in collisions:
        aliases.pop(suffix, None)
    return aliases


def region_type(value: str | None) -> str:
    value = compact_text(value or "")
    if not value:
        return "unknown"
    if value == "無し":
        return "none"
    if value in {"北海道", "東京都", "京都府", "大阪府"} or value.endswith("県"):
        return "domestic_prefecture"
    return "foreign_country"


def split_reference_denko_names(value: str, known_names: set[str], aliases: dict[str, str]) -> list[str]:
    raw = clean_reference_name(value)
    if not raw:
        return []
    if raw in known_names:
        return [raw]
    result: list[str] = []
    for comma_part in re.split(r"\s*[、,]\s*", raw):
        part = clean_reference_name(comma_part)
        if not part:
            continue
        if part in known_names:
            result.append(part)
            continue
        bullet_parts = [clean_reference_name(item) for item in re.split(r"\s*・\s*", part) if clean_reference_name(item)]
        if len(bullet_parts) > 1:
            resolved: list[str] = []
            for item in bullet_parts:
                resolved.append(aliases.get(item, item))
            result.extend(resolved)
        else:
            result.append(aliases.get(part, part))
    return unique_keep_order(result)


def normalize_station_name(value: str) -> str:
    value = compact_text(value)
    if not value:
        return value
    if "駅" in value or "スポット" in value:
        return value
    return f"{value}駅"


def split_reference_lines(value: str) -> list[str]:
    value = compact_text(value)
    if not value:
        return []
    value = value.replace("・（", "・ （")
    parts = [part.strip() for part in re.split(r"\s*・\s*", value) if part.strip()]
    merged: list[str] = []
    for part in parts:
        if merged and merged[-1].count("（") + merged[-1].count("(") > merged[-1].count("）") + merged[-1].count(")"):
            merged[-1] = f"{merged[-1]}・{part}"
        else:
            merged.append(part)
    cleaned: list[str] = []
    for part in merged:
        part = re.sub(r"\s+など$", "", part)
        part = re.sub(r"\s*\(\*\d+\)\s*", "", part)
        part = re.sub(r"\s*座標中心点住所：.*$", "", part)
        part = compact_text(part.strip("、。 "))
        if part:
            cleaned.append(part)
    return unique_keep_order(cleaned)


def extract_note_ids(value: str) -> list[str]:
    return unique_keep_order(re.findall(r"\*\d+", value or ""))


def extract_page_notes(soup: BeautifulSoup) -> dict[str, str]:
    notes: dict[str, str] = {}
    for text in soup.stripped_strings:
        match = re.match(r"【(\*\d+)】\s*(.+)", text)
        if match:
            notes[match.group(1)] = compact_text(match.group(2))
    return notes


def note_records(note_ids: list[str], notes: dict[str, str]) -> list[dict[str, str]]:
    return [
        {
            "marker": note_id,
            "text": notes.get(note_id, ""),
        }
        for note_id in note_ids
    ]


def reference_cache_text(page: dict[str, Any]) -> str:
    path = REFERENCE_CACHE_DIR / page["cache_name"]
    if not path.exists():
        REFERENCE_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        request = Request(page["url"], headers={"User-Agent": "Mozilla/5.0 prototype-reference-parser/0.1"})
        with urlopen(request, timeout=25) as response:
            content = response.read().decode(response.headers.get_content_charset() or "utf-8", errors="replace")
        path.write_text(content, encoding="utf-8")
        time.sleep(0.25)
    return path.read_text(encoding="utf-8-sig", errors="replace")


def parse_homecoming_reference(page: dict[str, Any], known_names: set[str], aliases: dict[str, str]) -> list[dict[str, Any]]:
    soup = BeautifulSoup(reference_cache_text(page), "html.parser")
    notes = extract_page_notes(soup)
    records: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        rows = table_to_grid(table)
        if not rows:
            continue
        header = rows[0]
        if not {"都道府県", "駅名", "路線名", "里帰りでんこ"}.issubset(set(header)):
            continue
        columns = {name: header.index(name) for name in ["都道府県", "駅名", "路線名", "里帰りでんこ"]}
        for row in rows[1:]:
            if len(row) <= max(columns.values()):
                continue
            prefecture = compact_text(row[columns["都道府県"]])
            station = normalize_station_name(row[columns["駅名"]])
            line_raw = row[columns["路線名"]]
            denko_raw = row[columns["里帰りでんこ"]]
            row_note_ids = unique_keep_order(extract_note_ids(line_raw) + extract_note_ids(station) + extract_note_ids(denko_raw))
            lines = split_reference_lines(line_raw)
            denko_names = split_reference_denko_names(denko_raw, known_names, aliases)
            if not station or not denko_names:
                continue
            for denko_name in denko_names:
                records.append(
                    {
                        "denko_name": denko_name,
                        "source_kind": page["source_kind"],
                        "source_label": page["label"],
                        "source_url": page["url"],
                        "priority": page["priority"],
                        "prefecture": prefecture,
                        "region_type": region_type(prefecture),
                        "station": station,
                        "lines": lines,
                        "line_raw": compact_text(line_raw),
                        "notes": note_records(row_note_ids, notes),
                    }
                )
    return records


def parse_prefecture_reference(page: dict[str, Any], known_names: set[str], aliases: dict[str, str]) -> list[dict[str, Any]]:
    soup = BeautifulSoup(reference_cache_text(page), "html.parser")
    records: list[dict[str, Any]] = []
    for table in soup.find_all("table"):
        rows = table_to_grid(table)
        if not rows:
            continue
        header = rows[0]
        prefecture_col = next((i for i, name in enumerate(header) if name in {"都道府県名", "国名 （一般的な名称）", "都道府県名・国名"}), None)
        if prefecture_col is None:
            continue
        denko_cols = [i for i, name in enumerate(header) if "でんこ" in name]
        for row in rows[1:]:
            if len(row) <= prefecture_col:
                continue
            prefecture = clean_reference_name(row[prefecture_col])
            if not prefecture:
                continue
            for col in denko_cols:
                if len(row) <= col:
                    continue
                for denko_name in split_reference_denko_names(row[col], known_names, aliases):
                    records.append(
                        {
                            "denko_name": denko_name,
                            "source_kind": page["source_kind"],
                            "source_label": page["label"],
                            "source_url": page["url"],
                            "priority": page["priority"],
                            "prefecture": prefecture,
                            "region_type": region_type(prefecture),
                            "station": None,
                            "lines": [],
                            "line_raw": None,
                            "notes": [],
                        }
                    )
    return records


def birthday_profile_denko_id(raw_no: str) -> str | None:
    raw_no = compact_text(raw_no)
    if not raw_no:
        return None
    if match := re.match(r"EX\s*(\d+)", raw_no, flags=re.IGNORECASE):
        return f"extra:{int(match.group(1)):03d}"
    if raw_no.isdigit():
        number = int(raw_no)
        if number > 0:
            return f"original:{number:03d}"
    return None


def parse_birthday_profile_reference(page: dict[str, Any]) -> dict[str, dict[str, Any]]:
    soup = BeautifulSoup(reference_cache_text(page), "html.parser")
    records: dict[str, dict[str, Any]] = {}
    for table in soup.find_all("table"):
        rows = table_to_grid(table)
        if not rows:
            continue
        header = rows[0]
        if not {"No.", "名前", "誕生日", "プロフィール"}.issubset(set(header)):
            continue
        columns = {name: header.index(name) for name in ["No.", "名前", "誕生日", "プロフィール"]}
        for row in rows[1:]:
            if len(row) <= max(columns.values()):
                continue
            denko_id = birthday_profile_denko_id(row[columns["No."]])
            if not denko_id:
                continue
            profile = compact_text(row[columns["プロフィール"]])
            full_name = profile.split("：", 1)[0] if "：" in profile else None
            records[denko_id] = {
                "denko_id": denko_id,
                "short_name": compact_text(row[columns["名前"]]),
                "full_name": full_name,
                "birthday": birthday_key(row[columns["誕生日"]]) or compact_text(row[columns["誕生日"]]),
                "profile_summary_raw": profile,
                "source_label": page["label"],
                "source_url": page["url"],
            }
    return records


def build_reference_lookup(known_names: set[str]) -> dict[str, list[dict[str, Any]]]:
    aliases = build_denko_name_resolver(known_names)
    records: list[dict[str, Any]] = []
    for page in REFERENCE_PAGES:
        if page["source_kind"].startswith("homecoming_station"):
            records.extend(parse_homecoming_reference(page, known_names, aliases))
        else:
            records.extend(parse_prefecture_reference(page, known_names, aliases))
    lookup: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        lookup.setdefault(record["denko_name"], []).append(record)
    for denko_name, items in lookup.items():
        lookup[denko_name] = sorted(items, key=lambda item: (-item["priority"], item["source_label"], item.get("station") or ""))
    return lookup


def reference_field_values(matches: list[dict[str, Any]], field: str, *, homecoming_only: bool = False) -> list[str]:
    eligible = [
        match
        for match in matches
        if not homecoming_only or str(match["source_kind"]).startswith("homecoming_station")
    ]
    if not eligible:
        return []
    max_priority = max(match["priority"] for match in eligible)
    values: list[str] = []
    for match in eligible:
        if match["priority"] < max_priority:
            continue
        value = match.get(field)
        if isinstance(value, list):
            values.extend(str(item) for item in value if item)
        elif value:
            values.append(str(value))
    return unique_keep_order(values)


def primary_reference_sources(matches: list[dict[str, Any]]) -> list[str]:
    homecoming = [match for match in matches if str(match["source_kind"]).startswith("homecoming_station")]
    eligible = homecoming or matches
    if not eligible:
        return []
    max_priority = max(match["priority"] for match in eligible)
    return unique_keep_order([match["source_label"] for match in eligible if match["priority"] == max_priority])


def primary_reference_links(matches: list[dict[str, Any]]) -> list[dict[str, str]]:
    homecoming = [match for match in matches if str(match["source_kind"]).startswith("homecoming_station")]
    eligible = homecoming or matches
    if not eligible:
        return []
    max_priority = max(match["priority"] for match in eligible)
    links: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in eligible:
        if match["priority"] != max_priority:
            continue
        key = (match["source_label"], match["source_url"])
        if key in seen:
            continue
        seen.add(key)
        links.append({"label": match["source_label"], "url": match["source_url"]})
    return links


def drop_substring_duplicates(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if any(item != other and item in other for other in items):
            continue
        result.append(item)
    return result


def has_sentence_fragment_noise(value: str) -> bool:
    noise_words = [
        "乗り入れる",
        "リンクしている",
        "地区および",
        "名のついた",
        "とは",
        "には",
        "また",
        "かつて",
        "を祈念",
        "存在した",
        "にある高架鉄道",
        "である高架鉄道",
        "主要駅",
        "地下駅",
        "モデル駅",
        "ターミナル駅",
        "高い駅",
        "意味する駅",
    ]
    return any(word in value for word in noise_words)


def strip_foreign_region_prefix(value: str) -> str:
    for prefix in FOREIGN_REGION_PREFIXES:
        dotted = f"{prefix}・"
        if value.startswith(dotted):
            return value.removeprefix(dotted)
    return value


def cleanup_station_candidate(value: str) -> str | None:
    value = compact_text(value)
    if "駅である" in value:
        value = value.rsplit("駅である", 1)[1]
    if "駅が" in value:
        value = value.rsplit("駅が", 1)[1]
    value = re.sub(r"^[のはがにある]+", "", value)
    value = re.sub(r"^.*の", "", value)
    value = re.sub(r"^(?:[一-龥ぁ-んァ-ヶA-Za-z0-9・ー]+(?:新幹線|本線|線|鉄道|電鉄|ライン))+", "", value)
    if value == "駅":
        return None
    if any(noise in value for noise in ["という駅", "名称の駅", "駅は存在しない"]):
        return None
    if re.search(r"(乗り入れる|リンクしている|地区および|名のついた|ターミナル|主要|地下|モデル|意味する|標高が高い|中心となる|付く駅|停車駅|元ネタ車両|始発駅|字を含む駅|名字が駅)", value):
        return None
    value = re.sub(r"^には", "", value)
    value = re.sub(r"^同地域には", "", value)
    if re.match(r"^[とを][ァ-ヶ一-龥]", value):
        return None
    if re.match(r"^[ぁ-ん][一-龥]駅$", value):
        return None
    if len(value) <= 2:
        return None
    return value


def cleanup_line_candidate(value: str) -> str | None:
    value = compact_text(value)
    value = re.sub(r"^[・\s]+", "", value)
    value = strip_foreign_region_prefix(value)
    if re.match(r"^[のはをやと]", value):
        return None
    salvage_patterns = [
        r"にある(.+)$",
        r"を走る(?:トラムの)?(.+)$",
        r"を拠点とする(.+)$",
        r"自体は(.+)$",
        r"思われる(.+)$",
        r"である(.+)$",
    ]
    for pattern in salvage_patterns:
        match = re.search(pattern, value)
        if match:
            value = compact_text(match.group(1))
            break
    if "駅は" in value:
        value = value.split("駅は", 1)[1]
    value = re.sub(r"^(?:トラムの|鉄道・バス)", "", value)
    if has_sentence_fragment_noise(value):
        return None
    if "スカイトレインの" in value:
        value = value.split("スカイトレインの", 1)[1]
    if any(fragment in value for fragment in ["モチーフ路線", "サッカー好き", "航空機の性能", "治安の悪さ", "開催を機に", "結ぶ路線", "繋がる路線"]):
        return None
    if any(fragment in value for fragment in ["営業廃止", "太陽光発電", "当路線", "保存鉄道", "元ネタ車両も", "株式会社の子会社", "協会の路線", "の線"]):
        return None
    if value in {"鉄道", "高架鉄道", "路線"}:
        return None
    if "駅は" in value:
        value = value.split("駅は", 1)[1]
    if re.match(r"^(?:の|は|を|や|と|という)", value):
        return None
    if len(value) <= 1:
        return None
    return value


def cleanup_operator_candidate(value: str) -> str | None:
    value = compact_text(value)
    value = re.sub(r"^[・\s]+", "", value)
    value = strip_foreign_region_prefix(value)
    if value in {"JR北海道", "JR東日本", "JR東海", "JR西日本", "JR四国", "JR九州", "JR貨物", "国鉄"}:
        return value
    if re.match(r"^[のはをやと]", value):
        return None
    salvage_patterns = [
        r"にある(.+)$",
        r"を走る(.+)$",
        r"を拠点とする(.+)$",
        r"自体は(.+)$",
        r"思われる(.+)$",
        r"である(.+)$",
        r"運行している(.+)$",
    ]
    for pattern in salvage_patterns:
        match = re.search(pattern, value)
        if match:
            value = compact_text(match.group(1))
            break
    if "駅は" in value:
        value = value.split("駅は", 1)[1]
    if has_sentence_fragment_noise(value):
        return None
    if any(fragment in value for fragment in ["にある", "である", "首都", "地域", "モデルとなった", "元ネタ車両", "カラーリング", "ゆかりのある駅", "沿線に鉄道", "名乗る鉄道", "保存鉄道", "間を結んでいた鉄道", "国有鉄道", "営業廃止", "株式会社の子会社"]):
        return None
    if re.match(r"^(?:の|は|を|や|と|という|上記)", value):
        return None
    if len(value) <= 2:
        return None
    return value


def extract_lines(text: str) -> list[str]:
    if not text:
        return []
    pattern = re.compile(r"([一-龥ぁ-んァ-ヶA-Za-z0-9・ー]+(?:新幹線|本線|線|鉄道|電鉄|ライン))")
    candidates = []
    for item in pattern.findall(text):
        if any(noise in item for noise in ["架線", "延線", "視線", "目線"]):
            continue
        cleaned = cleanup_line_candidate(item)
        if cleaned:
            if cleaned.count("線") >= 2 and "と" in cleaned:
                candidates.extend(part for part in re.split(r"\s*と\s*", cleaned) if part)
            else:
                candidates.append(cleaned)
    return unique_keep_order(candidates)


def extract_vehicles(text: str) -> list[str]:
    if not text:
        return []
    patterns = [
        r"([A-ZＡ-Ｚ]*\s*\d{2,4}形(?:\d+番台)?(?:\s*[（(][^）)]*[）)])?)",
        r"([A-ZＡ-Ｚ]*\s*\d{2,4}系(?:\d+番台)?(?:\s*[（(][^）)]*[）)])?)",
        r"(ドクターイエロー)",
        r"(オリエント急行)",
        r"([A-ZＡ-Ｚ]*\s*[A-ZＡ-Ｚ]{2,}\d+[A-ZＡ-Ｚ]*[A-Za-zＡ-Ｚ0-9]*)",
        r"([一-龥ぁ-んァ-ヶA-Za-z0-9・ー]+(?:洗浄車|確認車|延線車|保守用車|検測車|機関車))",
        r"(De\s*Lijn|TEC|MIVB|SNCB|NMBS)",
    ]
    found: list[str] = []
    for pattern in patterns:
        found.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    return drop_substring_duplicates(unique_keep_order(found))


def extract_operators(text: str) -> list[str]:
    if not text:
        return []
    patterns = [
        r"(JR北海道|JR東日本|JR東海|JR西日本|JR四国|JR九州|JR貨物)",
        r"([一-龥ぁ-んァ-ヶA-Za-z0-9・ー]+国鉄)",
        r"(国鉄)",
        r"([一-龥ぁ-んァ-ヶA-Za-z0-9・ー]+交通局)",
        r"([一-龥ぁ-んァ-ヶA-Za-z0-9・ー]+鉄道)",
        r"([一-龥ぁ-んァ-ヶA-Za-z0-9・ー]+電鉄)",
        r"(キウイレール|バンコク・スカイトレイン|ドバイメトロ|De\s*Lijn|TEC|MIVB|SNCB|NMBS|SNCF)",
    ]
    found: list[str] = []
    for pattern in patterns:
        found.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    cleaned = [item for item in (cleanup_operator_candidate(value) for value in found) if item]
    return drop_substring_duplicates(unique_keep_order(cleaned))


def extract_stations(text: str) -> list[str]:
    if not text:
        return []
    pattern = re.compile(r"([一-龥ぁ-んァ-ヶA-Za-z0-9・ー]+駅)")
    candidates = []
    for item in pattern.findall(text):
        cleaned = cleanup_station_candidate(item)
        if cleaned:
            candidates.append(cleaned)
    items = unique_keep_order(candidates)
    return [item for item in items if not any(item != other and item.endswith(other) for other in items)]


def extract_absent_station_names(text: str) -> list[str]:
    if not text:
        return []
    patterns = [
        r"「([^」]+)」(?:\([^)]*\))?という駅は存在しない",
        r"([一-龥ぁ-んァ-ヶA-Za-z0-9・ー]+)という名称の駅は[^。]*存在しない",
        r"([一-龥ぁ-んァ-ヶA-Za-z0-9・ー]+)という駅は存在しない",
    ]
    found: list[str] = []
    for pattern in patterns:
        found.extend(re.findall(pattern, text))
    return unique_keep_order(found)


def build_record(
    row: dict[str, Any],
    html_text: str,
    cache_meta: dict[str, Any],
    reference_lookup: dict[str, list[dict[str, Any]]],
    birthday_profile_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    identity = row["identity"]
    soup = BeautifulSoup(html_text, "html.parser")
    profile_raw = extract_section_text(soup, "プロフィール", max_chars=2500)
    name_origin_raw = extract_section_text(soup, "名前について", max_chars=1600)
    model_vehicle_raw = profile_field(profile_raw, "モデル車両・列車") or profile_field(profile_raw, "モデル車両")
    birthday_profile = birthday_profile_lookup.get(identity["denko_id"], {})
    detail_birthday = profile_field(profile_raw, "誕生日")
    birthday = birthday_profile.get("birthday") or detail_birthday
    voice_actor = profile_field(profile_raw, "声の担当") or profile_field(profile_raw, "担当声優")
    designer = profile_field(profile_raw, "キャラクターデザイン")
    combined = " ".join(item for item in [model_vehicle_raw, name_origin_raw] if item)
    operators = extract_operators(model_vehicle_raw or "") or extract_operators(combined)
    lines = extract_lines(combined)
    vehicles = extract_vehicles(model_vehicle_raw or combined)
    stations = extract_stations(name_origin_raw or "")
    absent_station_names = extract_absent_station_names(name_origin_raw or "")
    if model_vehicle_raw and not vehicles:
        vehicles = [model_vehicle_raw]

    reference_matches = reference_lookup.get(identity["name"], [])
    reference_stations = reference_field_values(reference_matches, "station", homecoming_only=True)
    reference_lines = reference_field_values(reference_matches, "lines", homecoming_only=True)
    homecoming_regions = reference_field_values(reference_matches, "prefecture", homecoming_only=True)
    all_reference_regions = unique_keep_order([str(match["prefecture"]) for match in reference_matches if match.get("prefecture")])
    regions = homecoming_regions or all_reference_regions
    prefectures = unique_keep_order(
        [value for value in regions if region_type(value) == "domestic_prefecture"]
    )
    countries = unique_keep_order(
        [value for value in all_reference_regions if region_type(value) == "foreign_country"]
    )
    no_place_regions = unique_keep_order([value for value in regions if region_type(value) == "none"])
    region_status = "unknown"
    if prefectures:
        region_status = "domestic"
    elif countries:
        region_status = "foreign"
    elif no_place_regions:
        region_status = "none"
    display_lines = reference_lines or lines
    display_stations = reference_stations or stations
    reference_sources = unique_keep_order([match["source_label"] for match in reference_matches])
    primary_sources = primary_reference_sources(reference_matches)
    primary_links = primary_reference_links(reference_matches)
    reference_notes = []
    for match in reference_matches:
        for note in match.get("notes") or []:
            if note.get("text"):
                reference_notes.append(
                    {
                        "source_label": match["source_label"],
                        "marker": note["marker"],
                        "text": note["text"],
                    }
                )
    reference_notes = unique_by_key(reference_notes, "text")

    evidence: list[dict[str, Any]] = []
    for field, source, text in [
        ("model_vehicle_raw", "プロフィール/モデル車両", model_vehicle_raw),
        ("name_origin_raw", "名前について", name_origin_raw),
        ("birthday", "生日・プロフィール一览/誕生日" if birthday_profile.get("birthday") else "プロフィール/誕生日", birthday),
        ("voice_actor", "プロフィール/声の担当", voice_actor),
    ]:
        if text:
            evidence.append({"field": field, "source_section": source, "text": text[:280], "confidence": "high"})
    if birthday_profile.get("profile_summary_raw"):
        evidence.append(
            {
                "field": "profile_summary_raw",
                "source_section": birthday_profile["source_label"],
                "source_url": birthday_profile["source_url"],
                "text": birthday_profile["profile_summary_raw"][:280],
                "confidence": "high",
            }
        )
    for match in unique_by_key(reference_matches, "source_kind"):
        evidence.append(
            {
                "field": "reference_matches",
                "source_section": match["source_label"],
                "source_url": match["source_url"],
                "text": compact_text(
                    " / ".join(
                        item
                        for item in [
                            match.get("prefecture"),
                            match.get("station"),
                            "、".join(match.get("lines") or []),
                        ]
                        if item
                    )
                )[:280],
                "confidence": "high",
            }
        )

    prompt_errors: list[str] = []
    if not name_origin_raw:
        prompt_errors.append("名前について欄を抽出できない")
    if model_vehicle_raw and not (vehicles or lines or operators):
        prompt_errors.append("モデル車両欄から会社/車両/路線候補を抽出できない")
    if not (operators or vehicles or display_lines or display_stations or absent_station_names or prefectures):
        prompt_errors.append("反查入口候補を抽出できない")

    confidence = "high" if not prompt_errors else "low"

    return {
        "denko_id": identity["denko_id"],
        "name": identity["name"],
        "pool": identity["pool"],
        "detail_url": identity["detail_url"],
        "birthday": birthday,
        "detail_birthday": detail_birthday,
        "voice_actor": voice_actor,
        "character_designer": designer,
        "profile_full_name": birthday_profile.get("full_name"),
        "profile_summary_raw": birthday_profile.get("profile_summary_raw"),
        "profile_section_raw": profile_raw,
        "model_vehicle_raw": model_vehicle_raw,
        "name_origin_raw": name_origin_raw,
        "reference_matches": reference_matches,
        "reference_sources": reference_sources,
        "primary_reference_sources": primary_sources,
        "primary_reference_links": primary_links,
        "reference_notes": reference_notes,
        "prototype_regions": regions,
        "prototype_prefectures": prefectures,
        "prototype_countries": countries,
        "prototype_region_status": region_status,
        "prototype_region_audit_reason": (
            "国内都道府県は返乡活动/都道府県別参考页确认"
            if prefectures
            else "外国でんことして国別参考页确认"
            if countries
            else "参考页为地名なし"
            if no_place_regions
            else "参考页未命中；详情页没有可确认的都道府県/国家字段"
        ),
        "no_place_regions": no_place_regions,
        "prototype_operators": operators,
        "prototype_lines": display_lines,
        "prototype_vehicles": vehicles,
        "prototype_stations": display_stations,
        "nearest_stations": display_stations,
        "detail_inferred_lines": lines,
        "detail_inferred_stations": stations,
        "absent_station_names": absent_station_names,
        "evidence": evidence,
        "confidence": confidence,
        "needs_llm": bool(prompt_errors),
        "prompt_errors": prompt_errors,
        "review_reasons": prompt_errors,
        "record_meta": {
            "source_url": identity["detail_url"],
            "content_hash": cache_meta["content_hash"],
            "parser_version": "prototype_sample_extract.v2.reference_priority",
            "parsed_at": now_iso(),
            "cache_path": cache_meta["cache_path"],
        },
    }


def voice_actor_keys(value: str | None) -> list[str]:
    if not value or value == "未実装":
        return []
    main = re.split(r"[（(]", value, maxsplit=1)[0]
    return unique_keep_order(re.split(r"[、/／]", main))


def birthday_key(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(\d{1,2})月(\d{1,2})日", value)
    if not match:
        return compact_text(value)
    return f"{int(match.group(1))}月{int(match.group(2))}日"


def birthday_sort_key(value: str) -> tuple[int, int, str]:
    match = re.search(r"(\d{1,2})月(\d{1,2})日", value)
    if not match:
        return (99, 99, value)
    return (int(match.group(1)), int(match.group(2)), value)


def katakana_to_hiragana(value: str) -> str:
    chars = []
    for ch in value:
        code = ord(ch)
        if 0x30A1 <= code <= 0x30F6:
            chars.append(chr(code - 0x60))
        else:
            chars.append(ch)
    return "".join(chars)


def normalized_search_text(value: str) -> str:
    value = compact_text(value).lower()
    variants = {
        value,
        value.replace(" ", ""),
        value.replace("・", ""),
        value.replace("＝", ""),
        value.replace("=", ""),
        value.replace("ヶ", "が"),
        value.replace("ヶ", "か"),
    }
    variants.update(katakana_to_hiragana(item) for item in list(variants))
    return " ".join(sorted(item for item in variants if item))


def reading_aliases(group: str, key: str) -> list[str]:
    aliases: list[str] = []
    if group == "by_prefecture":
        reading = PREFECTURE_READINGS.get(key)
        if reading:
            short = reading
            if key.endswith("県"):
                short = reading.removesuffix("けん")
            elif key.endswith("府"):
                short = reading.removesuffix("ふ")
            elif key.endswith("都"):
                short = reading.removesuffix("と")
            aliases.extend([reading, short])
        aliases.append(key.removesuffix("県").removesuffix("府").removesuffix("都").removesuffix("道"))
    elif group == "by_operator":
        if reading := OPERATOR_READINGS.get(key):
            aliases.append(reading)
        for name, reading in OPERATOR_READINGS.items():
            if name in key:
                aliases.append(reading)
    elif group == "by_station":
        if reading := STATION_READINGS.get(key):
            aliases.extend([reading, reading.removesuffix("えき")])
        aliases.append(key.removesuffix("駅"))
    elif group == "by_voice_actor":
        if reading := VOICE_ACTOR_READINGS.get(key):
            aliases.append(reading)
    elif group == "by_birthday":
        match = re.search(r"(\d{1,2})月(\d{1,2})日", key)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            aliases.extend([f"{month}月", f"{month}/{day}", f"{month}-{day}", f"{month:02d}{day:02d}"])
    return unique_keep_order([alias for alias in aliases if alias])


def directory_primary_reading(group: str, key: str) -> str:
    if group == "by_prefecture":
        return PREFECTURE_READINGS.get(key) or key
    if group == "by_operator":
        if key in OPERATOR_READINGS:
            return OPERATOR_READINGS[key]
        for name, reading in OPERATOR_READINGS.items():
            if name in key:
                return reading
    if group == "by_station":
        return STATION_READINGS.get(key) or key
    if group == "by_voice_actor":
        return VOICE_ACTOR_READINGS.get(key) or key
    return key


def directory_search_key(group: str, key: str) -> str:
    parts = [key, *reading_aliases(group, key)]
    return normalized_search_text(" ".join(parts))


def directory_section_label(group: str, key: str) -> str:
    if group == "by_birthday":
        month, _, _ = birthday_sort_key(key)
        return f"{month}月" if month != 99 else "#"
    initial = kana_initial(directory_primary_reading(group, key))
    if group in {"by_operator", "by_line", "by_voice_actor", "by_station", "by_vehicle", "by_absent_station_name"} and initial == "漢":
        return "#"
    return initial


def kana_initial(value: str) -> str:
    value = compact_text(value)
    if not value:
        return "#"
    ch = value[0]
    if ch.isascii() and ch.isalpha():
        return ch.upper()
    if ch.isdigit():
        return "#"
    groups = [
        ("あ", "あいうえおアイウエオ"),
        ("か", "かきくけこがぎぐげごカキクケコガギグゲゴ"),
        ("さ", "さしすせそざじずぜぞサシスセソザジズゼゾ"),
        ("た", "たちつてとだぢづでどタチツテトダヂヅデド"),
        ("な", "なにぬねのナニヌネノ"),
        ("は", "はひふへほばびぶべぼぱぴぷぺぽハヒフヘホバビブベボパピプペポ"),
        ("ま", "まみむめもマミムメモ"),
        ("や", "やゆよヤユヨ"),
        ("ら", "らりるれろラリルレロ"),
        ("わ", "わをんワヲン"),
    ]
    for label, chars in groups:
        if ch in chars:
            return label
    if "\u4e00" <= ch <= "\u9fff":
        return "漢"
    return "#"


def directory_sort_key(group: str, key: str) -> tuple[Any, ...]:
    if group == "by_birthday":
        month, day, label = birthday_sort_key(key)
        return (month, day, label)
    sort_text = directory_primary_reading(group, key)
    initial = kana_initial(sort_text)
    order = ["あ", "か", "さ", "た", "な", "は", "ま", "や", "ら", "わ", "漢", "#"]
    if group in {"by_operator", "by_line", "by_voice_actor", "by_station", "by_vehicle", "by_absent_station_name"}:
        order = ["あ", "か", "さ", "た", "な", "は", "ま", "や", "ら", "わ", "#", "漢"]
    rank = order.index(initial) if initial in order else 20
    return (rank, initial, sort_text, key)


def sorted_directory_entries(group: str, entries: dict[str, list[dict[str, str]]]) -> dict[str, list[dict[str, str]]]:
    return dict(sorted(entries.items(), key=lambda item: directory_sort_key(group, item[0])))


def is_reliable_for_default_index(record: dict[str, Any]) -> bool:
    return not record.get("needs_llm") and bool(record.get("evidence"))


def prompt_error_items(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "denko_id": record["denko_id"],
            "name": record["name"],
            "detail_url": record["detail_url"],
            "errors": record.get("prompt_errors") or [],
        }
        for record in records
        if record.get("prompt_errors")
    ]


def build_audit(records: list[dict[str, Any]]) -> dict[str, Any]:
    missing_birthday = [
        {"denko_id": record["denko_id"], "name": record["name"], "reason": "プロフィール/誕生日 未抽出"}
        for record in records
        if not record.get("birthday")
    ]
    missing_prefecture = []
    foreign = []
    no_place = []
    unknown_region = []
    for record in records:
        status = record.get("prototype_region_status")
        has_foreign_country = bool(record.get("prototype_countries"))
        has_domestic_prefecture = bool(record.get("prototype_prefectures"))
        item = {
            "denko_id": record["denko_id"],
            "name": record["name"],
            "detail_url": record["detail_url"],
            "regions": record.get("prototype_regions") or [],
            "countries": record.get("prototype_countries") or [],
        }
        if has_foreign_country:
            foreign.append(item)
        if status == "none":
            no_place.append(item)
        if status == "unknown":
            unknown_region.append(item)
            missing_prefecture.append({**item, "reason": record.get("prototype_region_audit_reason") or "参考页未命中，详情页未解析出国内都道府県"})
    return {
        "missing_birthday": missing_birthday,
        "missing_prefecture": missing_prefecture,
        "foreign_denko": foreign,
        "no_place_denko": no_place,
        "unknown_region": unknown_region,
        "counts": {
            "records": len(records),
            "missing_birthday": len(missing_birthday),
            "missing_prefecture_unknown": len(missing_prefecture),
            "foreign_denko": len(foreign),
            "no_place_denko": len(no_place),
            "domestic_denko": sum(1 for record in records if record.get("prototype_prefectures")),
        },
    }


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def denko_anchor(denko_id: str) -> str:
    return denko_id.replace(":", "-")


def directory_anchor_id(group: str, label: str) -> str:
    digest = hashlib.sha1(f"{group}:{label}".encode("utf-8")).hexdigest()[:10]
    return f"dir-{group}-{digest}"


def denko_ref(record: dict[str, Any]) -> dict[str, str]:
    return {
        "denko_id": record["denko_id"],
        "detail_url": record["detail_url"],
        "name": record["name"],
        "href": f"#{denko_anchor(record['denko_id'])}",
    }


def add_index_entry(index: dict[str, dict[str, list[dict[str, str]]]], group: str, key: str, record: dict[str, Any]) -> None:
    if not key:
        return
    bucket = index.setdefault(group, {}).setdefault(key, [])
    ref = denko_ref(record)
    if all(item["denko_id"] != ref["denko_id"] for item in bucket):
        bucket.append(ref)


def suspicious_index_keys(groups: dict[str, dict[str, list[dict[str, str]]]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    groups_to_check = {"by_absent_station_name"}
    for group, entries in groups.items():
        if group not in groups_to_check:
            continue
        for key, refs in entries.items():
            if len(refs) <= 1:
                continue
            issues.append(
                {
                    "group": group,
                    "key": key,
                    "denko_count": len(refs),
                    "denko": refs,
                    "reason": "命名来源 key 命中多个でんこ。可能是同姓/系列角色，也可能是解析或归一化需要复查。",
                }
            )
    return issues


def build_index(records: list[dict[str, Any]], source_records_path: Path = OUT_JSONL) -> dict[str, Any]:
    index: dict[str, dict[str, list[dict[str, str]]]] = {
        "by_prefecture": {},
        "by_foreign_country": {},
        "by_operator": {},
        "by_line": {},
        "by_voice_actor": {},
        "by_birthday": {},
    }
    hidden_index: dict[str, dict[str, list[dict[str, str]]]] = {
        "by_station": {},
        "by_vehicle": {},
        "by_absent_station_name": {},
    }
    for record in records:
        if not is_reliable_for_default_index(record):
            continue
        for prefecture in record.get("prototype_prefectures") or []:
            add_index_entry(index, "by_prefecture", prefecture, record)
        for country in record.get("prototype_countries") or []:
            add_index_entry(index, "by_foreign_country", country, record)
        for operator in record.get("prototype_operators") or []:
            add_index_entry(index, "by_operator", operator, record)
        for line in record.get("prototype_lines") or []:
            add_index_entry(index, "by_line", line, record)
        for station in record.get("prototype_stations") or []:
            add_index_entry(hidden_index, "by_station", station, record)
        for actor in voice_actor_keys(record.get("voice_actor")):
            add_index_entry(index, "by_voice_actor", actor, record)
        if key := birthday_key(record.get("birthday")):
            add_index_entry(index, "by_birthday", key, record)
        for vehicle in record.get("prototype_vehicles") or []:
            add_index_entry(hidden_index, "by_vehicle", vehicle, record)
        for station_name in record.get("absent_station_names") or []:
            add_index_entry(hidden_index, "by_absent_station_name", station_name, record)
    groups = {
        group: sorted_directory_entries(group, entries)
        for group, entries in index.items()
    }
    hidden_groups = {
        group: sorted_directory_entries(group, entries)
        for group, entries in hidden_index.items()
    }
    return {
        "schema_version": 1,
        "generated_at": now_iso(),
        "source_records": str(source_records_path.relative_to(ROOT)),
        "groups": groups,
        "hidden_groups": hidden_groups,
        "prompt_errors": prompt_error_items(records),
        "audit": build_audit(records),
    }


def render_directory_group(group: str, title: str, entries: dict[str, list[dict[str, str]]], empty_text: str = "暂无") -> str:
    if not entries:
        return f"""<section class="directory-card">
      <h2>{esc(title)}</h2>
      <p class="empty">{esc(empty_text)}</p>
    </section>"""
    items = []
    quick_links: list[str] = []
    last_initial: str | None = None
    for key, refs in entries.items():
        initial = directory_section_label(group, key)
        if initial != last_initial:
            header_id = directory_anchor_id(group, f"section:{initial}")
            quick_links.append(f"""<a href="#{esc(header_id)}">{esc(initial)}</a>""")
            items.append(f"""<li class="directory-section" id="{esc(header_id)}">{esc(initial)}</li>""")
            last_initial = initial
        links = " ".join(
            f"""<span class="denko-chip"><a href="{esc(ref['href'])}">{esc(ref['denko_id'])} {esc(ref['name'])}</a></span>"""
            for ref in refs
        )
        multi = f"""<span class="entry-count">{len(refs)}件</span>""" if len(refs) > 1 else ""
        item_id = directory_anchor_id(group, key)
        search_key = directory_search_key(group, key)
        items.append(
            f"""<li id="{esc(item_id)}" data-directory-item data-key="{esc(search_key)}"><span class="directory-key">{esc(key)}{multi}</span><span class="directory-links">{links}</span></li>"""
        )
    quick = f"""<nav class="directory-quick" aria-label="{esc(title)} 快速选择">{''.join(quick_links)}</nav>"""
    return f"""<section class="directory-card">
      <h2>{esc(title)}{'' if group == 'by_birthday' else f' <span>{len(entries)}</span>'}</h2>
      <div class="directory-tools">
        <input type="search" placeholder="搜索后跳转" aria-label="{esc(title)} 搜索" data-directory-search>
        <button type="button" data-directory-jump>跳转</button>
      </div>
      {quick}
      <ul class="directory-list">{''.join(items)}</ul>
    </section>"""


def render_collapsed_directory_group(group: str, title: str, entries: dict[str, list[dict[str, str]]], empty_text: str = "暂无") -> str:
    content = render_directory_group(group, title, entries, empty_text=empty_text)
    return f"""<details class="directory-details">
      <summary>{esc(title)} <span>{len(entries)}</span></summary>
      {content}
    </details>"""


def render_directory(index: dict[str, Any]) -> str:
    groups = index["groups"]
    hidden_groups = index["hidden_groups"]
    return f"""<section class="directory">
      {render_directory_group("by_prefecture", "都道府県入口", groups["by_prefecture"])}
      {render_directory_group("by_foreign_country", "外国でんこ入口", groups["by_foreign_country"])}
      {render_directory_group("by_operator", "公司/运营者入口", groups["by_operator"])}
      {render_directory_group("by_line", "线路入口", groups["by_line"])}
      {render_directory_group("by_voice_actor", "声优入口", groups["by_voice_actor"])}
      {render_directory_group("by_birthday", "生日入口", groups["by_birthday"])}
    </section>
    <section class="directory-collapsed">
      {render_collapsed_directory_group("by_station", "站点入口", hidden_groups["by_station"])}
      {render_collapsed_directory_group("by_vehicle", "车辆入口", hidden_groups["by_vehicle"])}
    </section>"""


def render_audit(index: dict[str, Any]) -> str:
    audit = index.get("audit") or {}
    counts = audit.get("counts") or {}
    unknown = audit.get("missing_prefecture") or []
    unknown_items = "".join(
        f"""<li><a href="#{esc(denko_anchor(item['denko_id']))}">{esc(item['denko_id'])} {esc(item['name'])}</a><span>{esc(item['reason'])}</span></li>"""
        for item in unknown[:40]
    )
    if len(unknown) > 40:
        unknown_items += f"""<li class="muted">另有 {len(unknown) - 40} 条未显示。</li>"""
    unknown_html = f"""<ul>{unknown_items}</ul>""" if unknown_items else """<p class="empty">无未知都道府県缺失项。</p>"""
    return f"""<details class="audit-card">
      <summary>数据检查 <span>生日缺失 {counts.get('missing_birthday', 0)} / 未知都道府県 {counts.get('missing_prefecture_unknown', 0)} / 外国でんこ {counts.get('foreign_denko', 0)} / 地名なし {counts.get('no_place_denko', 0)}</span></summary>
      <div class="audit-grid">
        <div><strong>生日</strong><p>当前 {counts.get('records', 0)} 条中缺失 {counts.get('missing_birthday', 0)} 条。</p></div>
        <div><strong>都道府県</strong><p>国内 {counts.get('domestic_denko', 0)} 条，外国 {counts.get('foreign_denko', 0)} 条，地名なし {counts.get('no_place_denko', 0)} 条，未知 {counts.get('missing_prefecture_unknown', 0)} 条。</p></div>
      </div>
      <h2>未知都道府県</h2>
      {unknown_html}
    </details>"""


def render_html(records: list[dict[str, Any]], dataset_label: str, source_records_path: Path) -> str:
    generated_at = now_iso()
    index = build_index(records, source_records_path=source_records_path)
    character_cards = []
    for record in records:
        source_links = record.get("primary_reference_links") or []
        if source_links:
            source_html = " ".join(
                f"""<a class="source-badge" href="{esc(item['url'])}" target="_blank" rel="noopener">{esc(item['label'])}</a>"""
                for item in source_links
            )
        else:
            source_html = f"""<a class="source-badge muted" href="{esc(record['detail_url'])}" target="_blank" rel="noopener">详情页</a>"""
        notes_html = ""
        if record.get("reference_notes"):
            notes = "".join(
                f"""<li><span>{esc(note['source_label'])} {esc(note['marker'])}</span>{esc(note['text'])}</li>"""
                for note in record["reference_notes"]
            )
            notes_html = f"""<article class="source-text reference-notes">
        <h3>参考注释</h3>
        <ul>{notes}</ul>
      </article>"""
        character_cards.append(
            f"""<section class="character-card" id="{esc(record['denko_id'].replace(':', '-'))}">
      <header class="character-card-header">
        <div>
          <h2>{esc(record['denko_id'])} {esc(record['name'])}</h2>
          <div class="card-subtitle"><a class="detail-link" href="{esc(record['detail_url'])}" target="_blank" rel="noopener">wiki页</a></div>
        </div>
      </header>
      <dl class="fact-grid">
        <div><dt>生日</dt><dd>{esc(record.get('birthday') or '-')}</dd></div>
        <div><dt>声优</dt><dd>{esc(record.get('voice_actor') or '-')}</dd></div>
        <div><dt>都道府県</dt><dd>{esc('、'.join(record.get('prototype_prefectures') or []) or '-')}</dd></div>
        <div><dt>国家/地区</dt><dd>{esc('、'.join(record.get('prototype_countries') or []) or '-')}</dd></div>
        <div><dt>公司/运营者</dt><dd>{esc('、'.join(record.get('prototype_operators') or []) or '-')}</dd></div>
        <div><dt>车辆候选</dt><dd>{esc('、'.join(record['prototype_vehicles']) or '-')}</dd></div>
        <div><dt>线路候选</dt><dd>{esc('、'.join(record['prototype_lines']) or '-')}</dd></div>
        <div><dt>站点候选</dt><dd>{esc('、'.join(record['prototype_stations']) or '-')}</dd></div>
        <div><dt>参考来源</dt><dd class="source-badge-list">{source_html}</dd></div>
      </dl>
      <article class="source-text">
        <h3>名前について</h3>
        <p>{esc(record.get('name_origin_raw') or '-')}</p>
      </article>
      {notes_html}
      <footer><a class="back-top" href="#top">返回顶部</a></footer>
    </section>"""
        )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Ekimemo 原型反查表</title>
  <style>
    body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; margin: 24px; color: #1f2328; line-height: 1.45; }}
    h1 {{ margin-bottom: 6px; }}
    h2 {{ margin-top: 24px; border-bottom: 1px solid #d8dee4; padding-bottom: 6px; }}
    .meta, .note {{ color: #68707c; font-size: 12px; }}
    .note {{ margin: 12px 0; }}
    .directory {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(220px, 1fr)); gap:12px; margin:16px 0 20px; }}
    .directory-card {{ border:1px solid #d8dee4; background:#fff; border-radius:4px; padding:10px; min-width:0; }}
    .directory-card h2 {{ margin:0 0 8px; font-size:15px; border:0; padding:0; }}
    .directory-card h2 span {{ color:#68707c; font-size:12px; }}
    .directory-tools {{ display:grid; grid-template-columns:minmax(0, 1fr) auto; gap:6px; margin-bottom:8px; }}
    .directory-tools input {{ min-width:0; border:1px solid #d0d7de; border-radius:4px; padding:5px 7px; font:inherit; font-size:12px; }}
    .directory-tools button {{ border:1px solid #d0d7de; border-radius:4px; background:#f6f8fa; color:#24292f; padding:5px 8px; font:inherit; font-size:12px; cursor:pointer; }}
    .directory-tools button:hover {{ background:#eef6ff; border-color:#8cbeef; }}
    .directory-quick {{ display:flex; flex-wrap:wrap; gap:4px; margin:0 0 8px; }}
    .directory-quick a {{ min-width:22px; text-align:center; border:1px solid #d0d7de; border-radius:4px; padding:1px 4px; color:#57606a; background:#fff; font-size:11px; font-weight:600; text-decoration:none; }}
    .directory-quick a:hover {{ background:#f6f8fa; color:#0969da; text-decoration:none; }}
    .directory-card ul {{ list-style:none; padding:0; margin:0; display:grid; gap:7px; }}
    .directory-list {{ max-height:520px; overflow:auto; overscroll-behavior:contain; padding-right:4px; scrollbar-gutter:stable; }}
    .directory-card li {{ display:grid; gap:3px; }}
    .directory-section {{ position:sticky; top:0; z-index:1; margin-top:2px; padding:2px 0; background:#fff; color:#68707c; font-size:11px; font-weight:700; border-bottom:1px solid #eef1f4; }}
    .directory-hit {{ outline:2px solid #f2cc60; outline-offset:2px; border-radius:4px; background:#fff8c5; }}
    .directory-key {{ font-weight:600; }}
    .directory-links {{ display:flex; flex-wrap:wrap; gap:6px; }}
    .denko-chip {{ display:inline-flex; align-items:center; gap:4px; border:1px solid #dbe7f3; border-radius:999px; padding:2px 6px; background:white; }}
    .detail-link, .back-top {{ font-size:12px; }}
    .back-top {{ font-weight:400; }}
    .entry-count {{ display:inline-block; margin-left:6px; color:#68707c; font-size:11px; font-weight:600; }}
    .directory-collapsed {{ display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:12px; margin:-8px 0 20px; }}
    .directory-details {{ border:1px dashed #d8dee4; border-radius:4px; background:#fff; padding:10px; }}
    .directory-details summary {{ cursor:pointer; font-weight:600; color:#68707c; }}
    .directory-details summary span {{ font-size:12px; }}
    .directory-details .directory-card {{ margin-top:10px; border:0; padding:0; background:transparent; }}
    .directory-details .directory-card h2 {{ display:none; }}
    .audit-card {{ border:1px solid #d8dee4; border-radius:6px; background:#fff; padding:12px; margin:14px 0 16px; }}
    .audit-card summary {{ cursor:pointer; font-weight:700; }}
    .audit-card summary span {{ color:#68707c; font-size:12px; font-weight:500; margin-left:8px; }}
    .audit-card h2 {{ margin:12px 0 8px; font-size:14px; border:0; padding:0; }}
    .audit-card ul {{ margin:0; padding-left:18px; }}
    .audit-card li {{ margin:4px 0; }}
    .audit-card li span {{ color:#68707c; margin-left:8px; }}
    .audit-grid {{ display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:10px; margin-top:10px; }}
    .audit-grid div {{ border:1px solid #d8dee4; border-radius:4px; padding:8px; background:#fbfcfe; }}
    .audit-grid p {{ margin:4px 0 0; color:#68707c; }}
    .empty {{ color:#68707c; margin:0; }}
    .character-list {{ display:grid; grid-template-columns:1fr; gap:14px; margin-top:18px; }}
    .character-card {{ border:1px solid #d8dee4; background:#fff; border-radius:6px; padding:14px; min-width:0; }}
    .character-card-header {{ display:flex; align-items:flex-start; justify-content:space-between; gap:12px; border-bottom:1px solid #d8dee4; padding-bottom:8px; margin-bottom:10px; }}
    .character-card h2 {{ margin:0; border:0; padding:0; font-size:18px; }}
    .card-subtitle {{ color:#68707c; font-size:12px; margin-top:4px; }}
    .fact-grid {{ display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); gap:8px 12px; margin:0 0 10px; }}
    .fact-grid div {{ min-width:0; }}
    .fact-grid dt {{ color:#68707c; font-size:12px; font-weight:600; }}
    .fact-grid dd {{ margin:2px 0 0; overflow-wrap:anywhere; }}
    .source-badge-list {{ display:flex; flex-wrap:wrap; gap:6px; }}
    .source-badge {{ display:inline-flex; align-items:center; min-height:22px; border:1px solid #d0d7de; background:#f6f8fa; color:#24292f; border-radius:999px; padding:2px 8px; font-size:12px; font-weight:600; text-decoration:none; }}
    .source-badge:hover {{ background:#eef6ff; border-color:#8cbeef; color:#0969da; text-decoration:none; }}
    .source-badge.muted {{ color:#68707c; font-weight:500; }}
    .source-text {{ border:1px solid #d8dee4; background:#fbfcfe; padding:12px; border-radius:6px; margin-top:10px; }}
    .source-text h3 {{ margin:0 0 8px; font-size:14px; color:#0969da; }}
    .source-text p {{ margin:0; line-height:1.65; white-space:pre-wrap; overflow-wrap:anywhere; }}
    .reference-notes ul {{ margin:0; padding-left:18px; }}
    .reference-notes li {{ margin:4px 0; }}
    .reference-notes span {{ color:#68707c; font-size:12px; margin-right:8px; }}
    .character-card footer {{ margin-top:10px; text-align:left; }}
    @media (max-width: 1400px) {{ .directory {{ grid-template-columns:repeat(3, minmax(0, 1fr)); }} }}
    @media (max-width: 1000px) {{ .directory, .directory-collapsed {{ grid-template-columns:repeat(2, minmax(0, 1fr)); }} }}
    @media (max-width: 900px) {{ .fact-grid {{ grid-template-columns:1fr; }} }}
    @media (max-width: 760px) {{ .directory, .directory-collapsed {{ grid-template-columns:1fr; }} }}
    code {{ background:#f6f8fa; padding:1px 4px; border-radius:4px; }}
    a {{ color: #0969da; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body id="top">
  <header>
    <h1>Ekimemo 原型反查表</h1>
    <div class="meta">generated_at: {esc(generated_at)} / {esc(dataset_label)}</div>
  </header>
  <main>
    <p class="note">展示层为中文；wiki 原文保留日语。当前为 {esc(dataset_label)}。</p>
    {render_audit(index)}
    {render_directory(index)}
    <section class="character-list">
      {''.join(character_cards)}
    </section>
  </main>
  <script>
    (() => {{
      const normalizeQuery = (value) => {{
        return value.trim().toLowerCase()
          .replace(/[\u30a1-\u30f6]/g, (ch) => String.fromCharCode(ch.charCodeAt(0) - 0x60))
          .replace(/[ ・＝=]/g, '');
      }};
      const scrollWithinList = (list, target, block = 'center') => {{
        const listRect = list.getBoundingClientRect();
        const targetRect = target.getBoundingClientRect();
        const current = list.scrollTop + targetRect.top - listRect.top;
        const offset = block === 'center' ? (list.clientHeight - target.offsetHeight) / 2 : 0;
        list.scrollTo({{ top: Math.max(0, current - offset), behavior: 'smooth' }});
      }};
      const jumpInCard = (card) => {{
        const input = card.querySelector('[data-directory-search]');
        const list = card.querySelector('.directory-list');
        if (!input || !list) return;
        const q = normalizeQuery(input.value);
        if (!q) return;
        const items = Array.from(list.querySelectorAll('[data-directory-item]'));
        const target = items.find((item) => (item.dataset.key || '').includes(q));
        if (!target) return;
        list.querySelectorAll('.directory-hit').forEach((item) => item.classList.remove('directory-hit'));
        target.classList.add('directory-hit');
        scrollWithinList(list, target);
      }};
      document.querySelectorAll('.directory-card').forEach((card) => {{
        const button = card.querySelector('[data-directory-jump]');
        const input = card.querySelector('[data-directory-search]');
        if (button) button.addEventListener('click', () => jumpInCard(card));
        if (input) input.addEventListener('keydown', (event) => {{
          if (event.key === 'Enter') {{
            event.preventDefault();
            jumpInCard(card);
          }}
        }});
      }});
      document.querySelectorAll('.directory-quick a').forEach((link) => {{
        link.addEventListener('click', (event) => {{
          const id = link.getAttribute('href')?.slice(1);
          if (!id) return;
          const target = document.getElementById(id);
          const list = link.closest('.directory-card')?.querySelector('.directory-list');
          if (!target || !list) return;
          event.preventDefault();
          scrollWithinList(list, target, 'start');
        }});
      }});
    }})();
  </script>
</body>
</html>
"""


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--all", action="store_true", help="Generate the full prototype lookup report.")
    parser.add_argument("--ids", nargs="*", help="Generate a focused subset. Defaults to the sample set.")
    args = parser.parse_args()

    denko_rows = read_jsonl(DENKO_FACTS)
    by_id = {row["identity"]["denko_id"]: row for row in denko_rows}
    if args.all:
        selected_ids = [row["identity"]["denko_id"] for row in denko_rows]
        out_jsonl = FULL_OUT_JSONL
        out_index_json = FULL_OUT_INDEX_JSON
        out_html = FULL_OUT_HTML
        dataset_label = f"full: {len(selected_ids)} denko"
    else:
        selected_ids = args.ids or SAMPLE_IDS
        out_jsonl = OUT_JSONL
        out_index_json = OUT_INDEX_JSON
        out_html = OUT_HTML
        dataset_label = "sample: original 001-005 + extra 001-005" if selected_ids == SAMPLE_IDS else f"subset: {len(selected_ids)} denko"
    reference_lookup = build_reference_lookup({row["identity"]["name"] for row in denko_rows})
    birthday_profile_lookup = parse_birthday_profile_reference(BIRTHDAY_PROFILE_PAGE)
    state = load_state()
    records: list[dict[str, Any]] = []
    for denko_id in selected_ids:
        row = by_id[denko_id]
        html_text, cache_meta = fetch_html(denko_id, row["identity"]["detail_url"], state, refresh=args.refresh)
        records.append(build_record(row, html_text, cache_meta, reference_lookup, birthday_profile_lookup))
    write_jsonl(out_jsonl, records)
    out_index_json.write_text(json.dumps(build_index(records, source_records_path=out_jsonl), ensure_ascii=False, indent=2), encoding="utf-8")
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(render_html(records, dataset_label, source_records_path=out_jsonl), encoding="utf-8")
    save_state(state)
    summary = {
        "html": str(out_html.relative_to(ROOT)),
        "index_json": str(out_index_json.relative_to(ROOT)),
        "jsonl": str(out_jsonl.relative_to(ROOT)),
        "state": str(STATE_PATH.relative_to(ROOT)),
        "records": len(records),
        "prompt_errors": prompt_error_items(records),
    }
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
