from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup, Tag

try:
    from unidecode import unidecode
except ImportError:  # pragma: no cover - optional display sorting helper
    unidecode = None


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

ADDITIONAL_STATION_READINGS = {
    "九頭竜湖駅": "くずりゅうこえき",
    "二見浦駅": "ふたみのうらえき",
    "伊万里駅": "いまりえき",
    "伊川谷駅": "いかわだにえき",
    "出戸駅": "でとえき",
    "出雲市駅": "いずもしえき",
    "北巽か南巽駅": "きたたつみかみなみたつみえき",
    "北野駅": "きたのえき",
    "南古谷駅": "みなみふるやえき",
    "南野駅": "みなみのえき",
    "博多駅": "はかたえき",
    "和田山駅": "わだやまえき",
    "四天王寺前夕陽ヶ丘駅": "してんのうじまえゆうひがおかえき",
    "天下茶屋駅": "てんがちゃやえき",
    "小倉駅": "こくらえき",
    "岩手石橋駅": "いわていしばしえき",
    "摩耶駅": "まやえき",
    "新山口駅": "しんやまぐちえき",
    "東京貨物ターミナル (スポット)": "とうきょうかもつたーみなる",
    "東京駅": "とうきょうえき",
    "東灘貨物駅": "ひがしなだかもつえき",
    "東灘駅": "ひがしなだえき",
    "江波駅": "えばえき",
    "江見駅": "えみえき",
    "牧之郷駅": "まきのこうえき",
    "神奈川新町駅": "かながわしんまちえき",
    "福住駅": "ふくずみえき",
    "豊橋駅": "とよはしえき",
    "里見駅": "さとみえき",
    "金沢文庫駅": "かなざわぶんこえき",
    "阿佐ケ谷駅": "あさがやえき",
    "阿蘇白川駅": "あそしらかわえき",
    "龍山駅": "よんさんえき",
    "龍陽路駅": "りゅうようろえき",
}
STATION_READINGS.update(ADDITIONAL_STATION_READINGS)

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

ADDITIONAL_OPERATOR_READINGS = {
    "上田電鉄": "うえだでんてつ",
    "京福電気鉄道": "けいふくでんきてつどう",
    "京阪電気鉄道": "けいはんでんきてつどう",
    "仙台市交通局": "せんだいしこうつうきょく",
    "名古屋鉄道": "なごやてつどう",
    "名古屋市交通局": "なごやしこうつうきょく",
    "大阪市交通局": "おおさかしこうつうきょく",
    "富士山麓鉄道": "ふじさんろくてつどう",
    "岩手開発鉄道": "いわてかいはつてつどう",
    "京浜急行電鉄": "けいひんきゅうこうでんてつ",
    "京王電鉄": "けいおうでんてつ",
    "千葉都市モノレール": "ちばとしものれーる",
    "台湾鉄路公司": "たいわんてつろこうし",
    "東京メトロ": "とうきょうめとろ",
    "東京モノレール": "とうきょうものれーる",
    "東武鉄道": "とうぶてつどう",
    "沖縄都市モノレール": "おきなわとしものれーる",
    "札幌市交通局": "さっぽろしこうつうきょく",
    "東京都交通局": "とうきょうとこうつうきょく",
    "松本電鉄": "まつもとでんてつ",
    "横浜高速鉄道": "よこはまこうそくてつどう",
    "水西高速鉄道": "すそこうそくてつどう",
    "神戸市交通局": "こうべしこうつうきょく",
    "西日本鉄道": "にしにっぽんてつどう",
    "西武鉄道": "せいぶてつどう",
    "秦皇島山海観光鉄道": "しんこうとうさんかいかんこうてつどう",
    "箱根登山鉄道": "はこねとざんてつどう",
    "野岩鉄道": "やがんてつどう",
    "阿佐海岸鉄道": "あさかいがんてつどう",
    "鹿児島市交通局": "かごしましこうつうきょく",
    "長崎電気軌道": "ながさきでんききどう",
    "阪堺電気軌道": "はんかいでんききどう",
    "阪急電鉄": "はんきゅうでんてつ",
    "黒部峡谷鉄道": "くろべきょうこくてつどう",
    "豊橋鉄道": "とよはしてつどう",
    "北勢鉄道": "ほくせいてつどう",
    "ロボスレイル": "ろぼすれいる",
    "ハウトレイン": "はうとれいん",
    "VRグループ": "ぶいあーるぐるーぷ",
    "フェロメックス": "ふぇろめっくす",
    "メキシコシティ・ライトレール": "めきしこしてぃらいとれーる",
    "ベルリンSバーン": "べるりんえすばーん",
    "上海トランスラピッド": "しゃんはいとらんすらぴっど",
    "伊豆急行": "いずきゅうこう",
    "国土交通省立山砂防工事専用軌道": "こくどこうつうしょうたてやまさぼうこうじせんようきどう",
    "埼玉新都市交通": "さいたましんとしこうつう",
    "天津開発区導軌電車": "てんしんかいはつくどうきでんしゃ",
    "宇都宮ライトレール": "うつのみやらいとれーる",
    "富士急行": "ふじきゅうこう",
    "愛知こどもの国": "あいちこどものくに",
    "智頭急行": "ちずきゅうこう",
    "首都圏新都市鉄道": "しゅとけんしんとしてつどう",
    "GOトランジット": "ごーとらんじっと",
}
OPERATOR_READINGS.update(ADDITIONAL_OPERATOR_READINGS)

LINE_READINGS = {
    "東京モノレール": "とうきょうものれーる",
    "2号線": "にごうせん",
    "9号線": "きゅうごうせん",
    "一畑電車北松江線": "いちばたでんしゃきたまつえせん",
    "上越新幹線": "じょうえつしんかんせん",
    "九州新幹線": "きゅうしゅうしんかんせん",
    "予土線": "よどせん",
    "京元線": "きょんうぉんせん",
    "京浜東北線": "けいひんとうほくせん",
    "京急本線": "けいきゅうほんせん",
    "東海道新幹線": "とうかいどうしんかんせん",
    "北海道新幹線": "ほっかいどうしんかんせん",
    "北陸新幹線": "ほくりくしんかんせん",
    "南北線": "なんぼくせん",
    "奥の細道最上川ライン": "おくのほそみちもがみがわらいん",
    "山陽新幹線": "さんようしんかんせん",
    "山陽線": "さんようせん",
    "常磐線": "じょうばんせん",
    "徳島線": "とくしません",
    "成田空港線": "なりたくうこうせん",
    "押上線": "おしあげせん",
    "日本海ひすいライン": "にほんかいひすいらいん",
    "東北新幹線": "とうほくしんかんせん",
    "森と水とロマンの鉄道": "もりとみずとろまんのてつどう",
    "牟岐線": "むぎせん",
    "生駒線": "いこません",
    "知多新線": "ちたしんせん",
    "総武線": "そうぶせん",
    "西九州新幹線": "にしきゅうしゅうしんかんせん",
    "北東線": "ほくとうせん",
    "八日市線": "ようかいちせん",
    "千葉都市モノレール２号線": "ちばとしものれーるにごうせん",
    "平渓線": "へいけいせん",
    "龍山線": "よんさんせん",
    "名鉄名古屋本線": "めいてつなごやほんせん",
    "豊橋鉄道東田本線": "とよはしてつどうあずまだほんせん",
    "北勢鉄道": "ほくせいてつどう",
    "三岐鉄道北勢線": "さんぎてつどうほくせいせん",
    "岩手開発鉄道": "いわてかいはつてつどう",
    "岩手開発鉄道日頃市線": "いわてかいはつてつどうひころいちせん",
    "タイ国有鉄道メークローン線": "たいこくゆうてつどうめーくろーんせん",
    "メキシコシティ地下鉄2号線": "めきしこしてぃちかてつにごうせん",
    "ベルリンSバーン": "べるりんえすばーん",
}

LINE_PREFIX_READINGS = {
    "一畑電車": "いちばたでんしゃ",
    "三陸鉄道": "さんりくてつどう",
    "上田電鉄": "うえだでんてつ",
    "京成": "けいせい",
    "京王": "けいおう",
    "京福電鉄": "けいふくでんてつ",
    "京阪": "けいはん",
    "仙台市営地下鉄": "せんだいしえいちかてつ",
    "伊豆急行": "いずきゅうこう",
    "伊豆箱根鉄道": "いずはこねてつどう",
    "伯備線": "はくびせん",
    "信楽高原鐵道": "しがらきこうげんてつどう",
    "内子線": "うちこせん",
    "南海": "なんかい",
    "南阿蘇鉄道": "みなみあそてつどう",
    "台湾鉄路公司": "たいわんてつろこうし",
    "名古屋市営地下鉄": "なごやしえいちかてつ",
    "名鉄": "めいてつ",
    "土佐くろしお鉄道": "とさくろしおてつどう",
    "埼玉新都市交通": "さいたましんとしこうつう",
    "富士山麓電気鉄道": "ふじさんろくでんきてつどう",
    "富士急行": "ふじきゅうこう",
    "小湊鉄道": "こみなとてつどう",
    "小田急": "おだきゅう",
    "山形鉄道": "やまがたてつどう",
    "山梨リニア": "やまなしりにあ",
    "島原鉄道": "しまばらてつどう",
    "嵯峨野観光鉄道": "さがのかんこうてつどう",
    "広電": "ひろでん",
    "智頭急行": "ちずきゅうこう",
    "札幌市営地下鉄": "さっぽろしえいちかてつ",
    "東京メトロ": "とうきょうめとろ",
    "東急": "とうきゅう",
    "東武": "とうぶ",
    "松本電鉄": "まつもとでんてつ",
    "松浦鉄道": "まつうらてつどう",
    "樽見鉄道": "たるみてつどう",
    "水西高速鉄道": "すそこうそくてつどう",
    "江ノ島電鉄": "えのしまでんてつ",
    "由利高原鉄道": "ゆりこうげんてつどう",
    "神戸市営地下鉄": "こうべしえいちかてつ",
    "福井鉄道": "ふくいてつどう",
    "秋田内陸縦貫鉄道": "あきたないりくじゅうかんてつどう",
    "秦皇島山海観光鉄道": "しんこうとうさんかいかんこうてつどう",
    "箱根登山鉄道": "はこねとざんてつどう",
    "西名古屋港線": "にしなごやこうせん",
    "西武": "せいぶ",
    "西鉄": "にしてつ",
    "近江鉄道": "おうみてつどう",
    "近鉄": "きんてつ",
    "道南いさりび鉄道": "どうなんいさりびてつどう",
    "都営": "とえい",
    "野岩鉄道": "やがんてつどう",
    "長崎電軌": "ながさきでんき",
    "長良川鉄道": "ながらがわてつどう",
    "阪堺電軌": "はんかいでんき",
    "阪急": "はんきゅう",
    "阿佐海岸鉄道": "あさかいがんてつどう",
    "青い森鉄道": "あおいもりてつどう",
    "韓国鉄道公社": "かんこくてつどうこうしゃ",
    "韓国鉄道": "かんこくてつどう",
    "首都圏広域急行鉄道": "しゅとけんこういききゅうこうてつどう",
    "鹿児島市電": "かごしましでん",
    "黒部峡谷鉄道": "くろべきょうこくてつどう",
}

LINE_OPERATOR_PREFIXES = {
    "JR山手線": "JR東日本",
    "JR京浜東北線": "JR東日本",
    "JR東北本線": "JR東日本",
    "JR日光線": "JR東日本",
    "JR常磐線": "JR東日本",
    "常磐線": "JR東日本",
    "JR奥羽本線": "JR東日本",
    "JR津軽線": "JR東日本",
    "JR城端線": "JR西日本",
    "JR氷見線": "JR西日本",
    "JR大村線": "JR九州",
    "JR佐世保線": "JR九州",
    "JR筑肥線": "JR九州",
    "JR土讃線": "JR四国",
    "JR陸羽西線": "JR東日本",
    "総武線": "JR東日本",
    "東北新幹線": "JR東日本",
    "東京メトロ": "東京メトロ",
    "東急": "東急電鉄",
    "京急": "京浜急行電鉄",
    "京成": "京成電鉄",
    "京王": "京王電鉄",
    "小田急": "小田急電鉄",
    "東武": "東武鉄道",
    "西武": "西武鉄道",
    "近鉄": "近畿日本鉄道",
    "阪急": "阪急電鉄",
    "阪堺電軌": "阪堺電気軌道",
    "南海": "南海電鉄",
    "西鉄": "西日本鉄道",
    "名鉄": "名古屋鉄道",
    "京阪": "京阪電気鉄道",
    "OsakaMetro": "OsakaMetro",
    "都営": "東京都交通局",
    "札幌市営地下鉄": "札幌市交通局",
    "仙台市営地下鉄": "仙台市交通局",
    "名古屋市営地下鉄": "名古屋市交通局",
    "神戸市営地下鉄": "神戸市交通局",
    "鹿児島市電": "鹿児島市交通局",
    "長崎電軌": "長崎電気軌道",
    "広電": "広島電鉄",
    "東京モノレール": "東京モノレール",
    "千葉都市モノレール": "千葉都市モノレール",
    "沖縄都市モノレール": "沖縄都市モノレール",
    "ゆいレール": "沖縄都市モノレール",
    "ハピラインふくい": "ハピラインふくい",
    "えちぜん鉄道": "えちぜん鉄道",
    "三岐鉄道": "三岐鉄道",
    "土佐くろしお鉄道": "土佐くろしお鉄道",
    "松浦鉄道": "松浦鉄道",
    "岩手開発鉄道": "岩手開発鉄道",
    "タイ国有鉄道": "タイ国有鉄道",
    "メキシコシティ地下鉄": "メキシコシティ地下鉄",
    "マルセイユトラム": "マルセイユ・トラム",
    "ソウル交通公社": "ソウル交通公社",
    "台湾鉄路公司": "台湾鉄路公司",
    "韓国鉄道公社": "韓国鉄道公社",
    "ベルリンSバーン": "ベルリンSバーン",
}

MODEL_OPERATOR_NAMES = [
    "東京メトロ",
    "東急",
    "京急",
    "京王",
    "小田急",
    "東武",
    "西武",
    "近鉄",
    "阪急",
    "南海",
    "西鉄",
    "OsakaMetro",
    "ハピラインふくい",
]

OPERATOR_ALIASES = {
    "東急": "東急電鉄",
    "京急": "京浜急行電鉄",
    "京王": "京王電鉄",
    "小田急": "小田急電鉄",
    "東武": "東武鉄道",
    "西武": "西武鉄道",
    "近鉄": "近畿日本鉄道",
    "阪急": "阪急電鉄",
    "南海": "南海電鉄",
    "西鉄": "西日本鉄道",
    "京阪": "京阪電気鉄道",
    "名鉄": "名古屋鉄道",
    "VR": "VRグループ",
    "台湾鉄路管理局": "台湾鉄路公司",
}

FOREIGN_DISPLAY_TRANSLATIONS: dict[str, dict[str, dict[str, str]]] = {
    "by_operator": {
        "GOトランジット": {"zh": "GO运输", "en": "GO Transit", "native": "GO Transit"},
        "VRグループ": {"zh": "芬兰VR集团", "en": "VR Group", "native": "VR Group"},
        "アイルランド国鉄": {"zh": "爱尔兰国铁", "en": "Iarnrod Eireann", "native": "Iarnrod Eireann"},
        "インド国鉄": {"zh": "印度铁路", "en": "Indian Railways", "native": "Indian Railways"},
        "インド鉄道": {"zh": "印度铁路", "en": "Indian Railways", "native": "Indian Railways"},
        "エストニア国鉄": {"zh": "爱沙尼亚铁路", "en": "Estonian Railways", "native": "Eesti Raudtee"},
        "カウアイ・プランテーション・レイルウェイ": {"zh": "考艾种植园铁路", "en": "Kauai Plantation Railway", "native": "Kauai Plantation Railway"},
        "クライストチャーチ・トラム": {"zh": "基督城有轨电车", "en": "Christchurch Tramway", "native": "Christchurch Tramway"},
        "サンフランシスコ・ケーブルカー": {"zh": "旧金山缆车", "en": "San Francisco cable car", "native": "San Francisco cable car"},
        "シュトースバーン": {"zh": "施图斯缆索铁路", "en": "Stoosbahn", "native": "Stoosbahn"},
        "スカイライン ドライバーレス・メトロ": {"zh": "檀香山天际线无人驾驶地铁", "en": "Skyline driverless metro", "native": "Skyline driverless metro"},
        "セントーサ・エクスプレス": {"zh": "圣淘沙捷运", "en": "Sentosa Express", "native": "Sentosa Express"},
        "シンガポールLRT センカン線": {"zh": "新加坡轻轨盛港线", "en": "Singapore LRT Sengkang line", "native": "Singapore LRT Sengkang line"},
        "ソウル交通公社2号線 新": {"zh": "首尔交通公社2号线 新", "en": "Seoul Metro Line 2 new", "native": "서울교통공사 2호선 신"},
        "タイ国有鉄道メークローン線 NKF型": {"zh": "泰国国铁美功线NKF型", "en": "State Railway of Thailand Maeklong Line NKF", "native": "การรถไฟแห่งประเทศไทย สายแม่กลอง NKF"},
        "デリー・メトロ": {"zh": "德里地铁", "en": "Delhi Metro", "native": "Delhi Metro"},
        "フランス国鉄": {"zh": "法国国铁", "en": "SNCF", "native": "SNCF"},
        "ベルギー国鉄": {"zh": "比利时国铁", "en": "SNCB / NMBS", "native": "SNCB / NMBS"},
        "上海トランスラピッド": {"zh": "上海磁浮", "en": "Shanghai Maglev", "native": "上海磁浮"},
        "韓国鉄道": {"zh": "韩国铁道公社", "en": "KORAIL", "native": "한국철도공사"},
    },
    "by_foreign_country": {
        "アイルランド": {"zh": "爱尔兰", "en": "Ireland", "native": "Ireland"},
        "アメリカ": {"zh": "美国", "en": "United States", "native": "United States"},
        "アラブ首長国連邦": {"zh": "阿拉伯联合酋长国", "en": "United Arab Emirates", "native": "United Arab Emirates"},
        "アルゼンチン": {"zh": "阿根廷", "en": "Argentina", "native": "Argentina"},
        "イギリス": {"zh": "英国", "en": "United Kingdom", "native": "United Kingdom"},
        "イタリア": {"zh": "意大利", "en": "Italy", "native": "Italia"},
        "インド": {"zh": "印度", "en": "India", "native": "India"},
        "エジプト": {"zh": "埃及", "en": "Egypt", "native": "Egypt"},
        "エストニア": {"zh": "爱沙尼亚", "en": "Estonia", "native": "Eesti"},
        "オランダ": {"zh": "荷兰", "en": "Netherlands", "native": "Nederland"},
        "オーストラリア": {"zh": "澳大利亚", "en": "Australia", "native": "Australia"},
        "カナダ": {"zh": "加拿大", "en": "Canada", "native": "Canada"},
        "ギリシャ": {"zh": "希腊", "en": "Greece", "native": "Ελλάδα"},
        "シンガポール": {"zh": "新加坡", "en": "Singapore", "native": "Singapore"},
        "ジンバブエ": {"zh": "津巴布韦", "en": "Zimbabwe", "native": "Zimbabwe"},
        "スイス": {"zh": "瑞士", "en": "Switzerland", "native": "Schweiz / Suisse / Svizzera"},
        "スペイン": {"zh": "西班牙", "en": "Spain", "native": "España"},
        "タイ": {"zh": "泰国", "en": "Thailand", "native": "ประเทศไทย"},
        "トルコ": {"zh": "土耳其", "en": "Turkey", "native": "Türkiye"},
        "ドイツ": {"zh": "德国", "en": "Germany", "native": "Deutschland"},
        "ニュージーランド": {"zh": "新西兰", "en": "New Zealand", "native": "New Zealand / Aotearoa"},
        "フィンランド": {"zh": "芬兰", "en": "Finland", "native": "Suomi"},
        "フランス": {"zh": "法国", "en": "France", "native": "France"},
        "ブラジル": {"zh": "巴西", "en": "Brazil", "native": "Brasil"},
        "ベトナム": {"zh": "越南", "en": "Vietnam", "native": "Việt Nam"},
        "ベルギー": {"zh": "比利时", "en": "Belgium", "native": "België / Belgique"},
        "ペルー": {"zh": "秘鲁", "en": "Peru", "native": "Perú"},
        "メキシコ": {"zh": "墨西哥", "en": "Mexico", "native": "México"},
        "ラトビア": {"zh": "拉脱维亚", "en": "Latvia", "native": "Latvija"},
        "リトアニア": {"zh": "立陶宛", "en": "Lithuania", "native": "Lietuva"},
        "ロシア": {"zh": "俄罗斯", "en": "Russia", "native": "Россия"},
        "中国": {"zh": "中国", "en": "China", "native": "中国"},
        "南アフリカ": {"zh": "南非", "en": "South Africa", "native": "South Africa"},
        "台湾": {"zh": "台湾", "en": "Taiwan", "native": "台灣"},
        "韓国": {"zh": "韩国", "en": "South Korea", "native": "대한민국"},
    },
    "by_line": {
        "A線": {"zh": "RER A线", "en": "RER A line", "native": "RER A"},
        "B線": {"zh": "RER B线", "en": "RER B line", "native": "RER B"},
        "C線": {"zh": "RER C线", "en": "RER C line", "native": "RER C"},
        "GOトランジット・レイクショア・ウェスト線": {"zh": "GO运输湖滨西线", "en": "GO Transit Lakeshore West line", "native": "Lakeshore West line"},
        "SR水西平沢高速線": {"zh": "SR水西平泽高速线", "en": "Suseo-Pyeongtaek high-speed railway", "native": "수서평택고속선"},
        "T2号線": {"zh": "伊斯坦布尔T2线", "en": "Istanbul tram T2 line", "native": "T2 hattı"},
        "T3号線": {"zh": "伊斯坦布尔T3线", "en": "Istanbul tram T3 line", "native": "T3 hattı"},
        "アフダル線": {"zh": "阿赫达尔线", "en": "Al Akhdar line", "native": "Al Akhdar line"},
        "アラスカ鉄道": {"zh": "阿拉斯加铁路", "en": "Alaska Railroad", "native": "Alaska Railroad"},
        "アルブラ線": {"zh": "阿尔布拉线", "en": "Albula line", "native": "Albulalinie"},
        "イギリス鉄道": {"zh": "英国铁路", "en": "British railway", "native": "British railway"},
        "インド鉄道": {"zh": "印度铁路", "en": "Indian Railways", "native": "Indian Railways"},
        "ウェスト・コースト鉄道": {"zh": "西海岸铁路", "en": "West Coast Railways", "native": "West Coast Railways"},
        "ウェスト・ハイランド線": {"zh": "西高地线", "en": "West Highland Line", "native": "West Highland Line"},
        "エジプト鉄道": {"zh": "埃及铁路", "en": "Egyptian National Railways", "native": "Egyptian National Railways"},
        "オランダ鉄道": {"zh": "荷兰铁路", "en": "Nederlandse Spoorwegen", "native": "Nederlandse Spoorwegen"},
        "カイロ地下鉄1号線": {"zh": "开罗地铁1号线", "en": "Cairo Metro Line 1", "native": "Cairo Metro Line 1"},
        "キウイレール・ミッドランド線": {"zh": "KiwiRail米德兰线", "en": "KiwiRail Midland Line", "native": "Midland Line"},
        "グランドキャニオン鉄道": {"zh": "大峡谷铁路", "en": "Grand Canyon Railway", "native": "Grand Canyon Railway"},
        "グレート・ウェスタン鉄道": {"zh": "大西部铁路", "en": "Great Western Railway", "native": "Great Western Railway"},
        "コラライン": {"zh": "珊瑚线", "en": "Coral line", "native": "Coral line"},
        "シベリア鉄道": {"zh": "西伯利亚铁路", "en": "Trans-Siberian Railway", "native": "Транссибирская магистраль"},
        "シルバーライン": {"zh": "银线", "en": "Silver Line", "native": "Silver Line"},
        "シーロム線": {"zh": "是隆线", "en": "Silom Line", "native": "สายสีลม"},
        "スイスMOB鉄道": {"zh": "瑞士MOB铁路", "en": "Montreux Oberland Bernois Railway", "native": "Chemin de fer Montreux Oberland bernois"},
        "スカイライン": {"zh": "檀香山天际线", "en": "Skyline", "native": "Skyline"},
        "スクムウィット線": {"zh": "素坤逸线", "en": "Sukhumvit Line", "native": "สายสุขุมวิท"},
        "センカン線": {"zh": "盛港线", "en": "Sengkang LRT line", "native": "Sengkang LRT line"},
        "ソウル交通公社2号線": {"zh": "首尔地铁2号线", "en": "Seoul Subway Line 2", "native": "서울 지하철 2호선"},
        "タイエリ峡谷鉄道": {"zh": "泰伊里峡谷铁路", "en": "Taieri Gorge Railway", "native": "Taieri Gorge Railway"},
        "タイ国有鉄道メークローン線": {"zh": "泰国国铁美功线", "en": "Maeklong Railway", "native": "ทางรถไฟสายแม่กลอง"},
        "タイ国有鉄道北本線": {"zh": "泰国国铁北本线", "en": "Northern Line", "native": "ทางรถไฟสายเหนือ"},
        "ダニーデン鉄道": {"zh": "达尼丁铁路", "en": "Dunedin Railways", "native": "Dunedin Railways"},
        "ダージリン・ヒマラヤ鉄道": {"zh": "大吉岭喜马拉雅铁路", "en": "Darjeeling Himalayan Railway", "native": "Darjeeling Himalayan Railway"},
        "ドイツ鉄道": {"zh": "德国铁路", "en": "Deutsche Bahn", "native": "Deutsche Bahn"},
        "ドバイメトロアフマル線": {"zh": "迪拜地铁红线", "en": "Dubai Metro Red Line", "native": "Red Line"},
        "ハウトレイン": {"zh": "豪登列车", "en": "Gautrain", "native": "Gautrain"},
        "ハワイ鉄道": {"zh": "夏威夷铁路", "en": "Hawaiian Railway", "native": "Hawaiian Railway"},
        "バイロンベイ鉄道": {"zh": "拜伦湾铁路", "en": "Byron Bay Train", "native": "Byron Bay Train"},
        "パッフィンビリー鉄道": {"zh": "普芬比利铁路", "en": "Puffing Billy Railway", "native": "Puffing Billy Railway"},
        "ベトナム鉄道南北線": {"zh": "越南铁路南北线", "en": "North-South Railway", "native": "Đường sắt Bắc Nam"},
        "ベルリンSバーン": {"zh": "柏林城市快铁", "en": "Berlin S-Bahn", "native": "S-Bahn Berlin"},
        "ペリオン鉄道": {"zh": "皮立翁铁路", "en": "Pelion railway", "native": "Pelion railway"},
        "ペルー鉄道": {"zh": "秘鲁铁路", "en": "PeruRail", "native": "PeruRail"},
        "マルセイユトラム1号線": {"zh": "马赛有轨电车1号线", "en": "Marseille tramway line 1", "native": "Ligne 1 du tramway de Marseille"},
        "マルセイユトラム2号線": {"zh": "马赛有轨电车2号线", "en": "Marseille tramway line 2", "native": "Ligne 2 du tramway de Marseille"},
        "メイソン線": {"zh": "梅森线", "en": "Mason line", "native": "Mason line"},
        "メキシコシティ地下鉄2号線": {"zh": "墨西哥城地铁2号线", "en": "Mexico City Metro Line 2", "native": "Línea 2"},
        "メキシコシティ地下鉄9号線": {"zh": "墨西哥城地铁9号线", "en": "Mexico City Metro Line 9", "native": "Línea 9"},
        "モントルー・オーベルラン・ベルノワ鉄道": {"zh": "蒙特勒-伯尔尼高地铁路", "en": "Montreux Oberland Bernois Railway", "native": "Chemin de fer Montreux Oberland bernois"},
        "リトアニア鉄道": {"zh": "立陶宛铁路", "en": "Lithuanian Railways", "native": "Lietuvos geležinkeliai"},
        "レーティッシュ鉄道ベルニナ線": {"zh": "雷蒂亚铁路伯尔尼纳线", "en": "Bernina line", "native": "Berninalinie"},
        "ロシア鉄道": {"zh": "俄罗斯铁路", "en": "Russian Railways", "native": "Российские железные дороги"},
        "ロッキーマウンテニア鉄道": {"zh": "落基山登山者列车", "en": "Rocky Mountaineer", "native": "Rocky Mountaineer"},
        "ヴィトーリア・ミナス鉄道": {"zh": "维多利亚-米纳斯铁路", "en": "Vitória-Minas Railway", "native": "Estrada de Ferro Vitória a Minas"},
        "ヴィリニュス鉄道": {"zh": "维尔纽斯铁路", "en": "Vilnius railway", "native": "Vilnius railway"},
        "ヴェルデ・キャニオン鉄道": {"zh": "佛得峡谷铁路", "en": "Verde Canyon Railroad", "native": "Verde Canyon Railroad"},
        "ヴッパータール空中鉄道": {"zh": "伍珀塔尔悬挂铁路", "en": "Wuppertal Schwebebahn", "native": "Wuppertaler Schwebebahn"},
        "京元線": {"zh": "京元线", "en": "Gyeongwon Line", "native": "경원선"},
        "北東線": {"zh": "东北线", "en": "North East MRT line", "native": "North East MRT line"},
        "南北線": {"zh": "南北线", "en": "North-South MRT line", "native": "North-South MRT line"},
        "台湾鉄路公司平渓線": {"zh": "台铁平溪线", "en": "Pingxi line", "native": "平溪線"},
        "水西高速鉄道": {"zh": "水西高速铁路", "en": "Suseo high-speed railway", "native": "수서고속철도"},
        "秦皇島山海観光鉄道": {"zh": "秦皇岛山海观光铁路", "en": "Qinhuangdao Shanhai Tourist Railway", "native": "秦皇岛山海旅游铁路"},
        "韓国鉄道公社・空港鉄道": {"zh": "韩国铁道公社/机场铁路", "en": "KORAIL / Airport Railroad", "native": "한국철도공사 / 공항철도"},
        "韓国鉄道公社京釜線": {"zh": "京釜线", "en": "Gyeongbu Line", "native": "경부선"},
        "首都圏広域急行鉄道A路線": {"zh": "首都圈广域急行铁路A线", "en": "GTX Line A", "native": "수도권 광역급행철도 A노선"},
        "龍山線": {"zh": "龙山线", "en": "Yongsan Line", "native": "용산선"},
    },
    "by_station": {
        "Bellevue駅": {"zh": "贝尔维尤站", "en": "Bellevue station", "native": "Bellevue"},
        "アトランティス・アクアベンチャー駅": {"zh": "亚特兰蒂斯水世界站", "en": "Atlantis Aquaventure station", "native": "Atlantis Aquaventure"},
        "アトーチャ駅": {"zh": "阿托查站", "en": "Atocha station", "native": "Atocha"},
        "アンカレッジ駅": {"zh": "安克雷奇站", "en": "Anchorage station", "native": "Anchorage"},
        "アントウェルペン中央駅": {"zh": "安特卫普中央站", "en": "Antwerp Central station", "native": "Antwerpen-Centraal"},
        "イマンタ駅": {"zh": "伊曼塔站", "en": "Imanta station", "native": "Imanta"},
        "イースト・カポレイ駅": {"zh": "东卡波雷站", "en": "East Kapolei station", "native": "East Kapolei"},
        "ウィリアムス駅": {"zh": "威廉姆斯站", "en": "Williams station", "native": "Williams"},
        "エル・ラムル駅": {"zh": "拉姆勒站", "en": "El Raml station", "native": "El Raml"},
        "オペラ駅": {"zh": "歌剧院站", "en": "Opéra station", "native": "Opéra"},
        "オリャンタイタンボ駅": {"zh": "奥良泰坦博站", "en": "Ollantaytambo station", "native": "Ollantaytambo"},
        "オーバーバルメン駅": {"zh": "上巴门站", "en": "Oberbarmen station", "native": "Oberbarmen"},
        "クアラカイ駅": {"zh": "库阿拉凯站", "en": "Kualakaʻi station", "native": "Kualakaʻi"},
        "クラークデール駅": {"zh": "克拉克代尔站", "en": "Clarkdale station", "native": "Clarkdale"},
        "グレンフィナン駅": {"zh": "格伦芬南站", "en": "Glenfinnan station", "native": "Glenfinnan"},
        "サイアム駅": {"zh": "暹罗站", "en": "Siam station", "native": "สถานีสยาม"},
        "サンタバーバラ駅": {"zh": "圣巴巴拉站", "en": "Santa Barbara station", "native": "Santa Barbara"},
        "シシハネ駅": {"zh": "希什哈内站", "en": "Şişhane station", "native": "Şişhane"},
        "シャトー駅": {"zh": "城堡站", "en": "Château station", "native": "Château"},
        "ジャスパー駅": {"zh": "贾斯珀站", "en": "Jasper station", "native": "Jasper"},
        "ジュメイラ・ビーチ・レジデンス1駅": {"zh": "朱美拉海滩公寓1站", "en": "Jumeirah Beach Residence 1 station", "native": "Jumeirah Beach Residence 1"},
        "ジュメイラ・ビーチ・レジデンス2駅": {"zh": "朱美拉海滩公寓2站", "en": "Jumeirah Beach Residence 2 station", "native": "Jumeirah Beach Residence 2"},
        "ジュメイラ・レイク・タワーズ駅": {"zh": "朱美拉湖塔站", "en": "Jumeirah Lakes Towers station", "native": "Jumeirah Lakes Towers"},
        "スプリングフィールド駅": {"zh": "斯普林菲尔德站", "en": "Springfield station", "native": "Springfield"},
        "センカン駅": {"zh": "盛港站", "en": "Sengkang station", "native": "Sengkang"},
        "セント・パンクラス駅": {"zh": "圣潘克拉斯站", "en": "St Pancras station", "native": "St Pancras"},
        "ソウル駅": {"zh": "首尔站", "en": "Seoul station", "native": "서울역"},
        "ソチミルコ駅": {"zh": "霍奇米尔科站", "en": "Xochimilco station", "native": "Xochimilco"},
        "タクバヤ駅": {"zh": "塔库巴亚站", "en": "Tacubaya station", "native": "Tacubaya"},
        "タスケーニャ駅": {"zh": "塔斯克尼亚站", "en": "Tasqueña station", "native": "Tasqueña"},
        "タルトゥ駅": {"zh": "塔尔图站", "en": "Tartu station", "native": "Tartu"},
        "ダージリン駅": {"zh": "大吉岭站", "en": "Darjeeling station", "native": "Darjeeling"},
        "チェンマイ駅": {"zh": "清迈站", "en": "Chiang Mai station", "native": "สถานีเชียงใหม่"},
        "チャトラパティ・シヴァージー・ターミナス駅": {"zh": "贾特拉帕蒂·希瓦吉终点站", "en": "Chhatrapati Shivaji Terminus", "native": "Chhatrapati Shivaji Terminus"},
        "デン・ハーグHS駅": {"zh": "海牙HS站", "en": "Den Haag HS station", "native": "Den Haag HS"},
        "デン・ハーグ中央駅": {"zh": "海牙中央站", "en": "Den Haag Centraal station", "native": "Den Haag Centraal"},
        "デ・パンネ駅": {"zh": "德潘讷站", "en": "De Panne station", "native": "De Panne"},
        "ナイアガラ・フォールズ駅": {"zh": "尼亚加拉瀑布站", "en": "Niagara Falls station", "native": "Niagara Falls"},
        "ナイアガラ駅": {"zh": "尼亚加拉站", "en": "Niagara station", "native": "Niagara"},
        "ニューデリー駅": {"zh": "新德里站", "en": "New Delhi station", "native": "New Delhi"},
        "ノアイユ駅": {"zh": "诺阿耶站", "en": "Noailles station", "native": "Noailles"},
        "ハウステンボス駅": {"zh": "豪斯登堡站", "en": "Huis Ten Bosch station", "native": "Huis Ten Bosch"},
        "ハットフィールド駅": {"zh": "哈特菲尔德站", "en": "Hatfield station", "native": "Hatfield"},
        "ハノイ駅": {"zh": "河内站", "en": "Hanoi station", "native": "Ga Hà Nội"},
        "バイロンベイ駅": {"zh": "拜伦湾站", "en": "Byron Bay station", "native": "Byron Bay"},
        "パウエル駅": {"zh": "鲍威尔站", "en": "Powell station", "native": "Powell"},
        "パリ北駅": {"zh": "巴黎北站", "en": "Paris-Nord station", "native": "Gare du Nord"},
        "ヒューストン駅": {"zh": "休斯顿站", "en": "Heuston station", "native": "Heuston"},
        "ビネンホフ駅": {"zh": "内庭站", "en": "Binnenhof station", "native": "Binnenhof"},
        "フォーヴィンケル駅": {"zh": "福温克尔站", "en": "Vohwinkel station", "native": "Vohwinkel"},
        "ブラッデル駅": {"zh": "布莱德站", "en": "Braddell station", "native": "Braddell"},
        "ブルジュマーン駅": {"zh": "布尔朱曼站", "en": "BurJuman station", "native": "BurJuman"},
        "ヘルシンキ中央駅": {"zh": "赫尔辛基中央站", "en": "Helsinki Central station", "native": "Helsingin päärautatieasema"},
        "ベイオール駅": {"zh": "贝伊奥卢站", "en": "Beyoğlu station", "native": "Beyoğlu"},
        "ベルリン中央駅": {"zh": "柏林中央站", "en": "Berlin Hauptbahnhof", "native": "Berlin Hauptbahnhof"},
        "ベロオリゾンテ駅": {"zh": "贝洛奥里藏特站", "en": "Belo Horizonte station", "native": "Belo Horizonte"},
        "マクリーン駅": {"zh": "麦克莱恩站", "en": "McLean station", "native": "McLean"},
        "マドリード駅": {"zh": "马德里站", "en": "Madrid station", "native": "Madrid"},
        "ミリエス駅": {"zh": "米利埃斯站", "en": "Milies station", "native": "Milies"},
        "メークローン駅": {"zh": "美功站", "en": "Maeklong station", "native": "สถานีแม่กลอง"},
        "モスクワ駅": {"zh": "莫斯科站", "en": "Moscow station", "native": "Москва"},
        "モスコフスキー駅": {"zh": "莫斯科夫斯基站", "en": "Moskovsky station", "native": "Московский вокзал"},
        "ユトレヒト中央駅": {"zh": "乌得勒支中央站", "en": "Utrecht Centraal", "native": "Utrecht Centraal"},
        "ユニオン駅": {"zh": "联合车站", "en": "Union Station", "native": "Union Station"},
        "ヨハネスブルグ・パーク駅": {"zh": "约翰内斯堡公园站", "en": "Johannesburg Park Station", "native": "Johannesburg Park Station"},
        "レティーロ駅": {"zh": "雷蒂罗站", "en": "Retiro station", "native": "Retiro"},
        "ヴァンセンヌ駅": {"zh": "万塞讷站", "en": "Vincennes station", "native": "Vincennes"},
        "ヴィリニュス駅": {"zh": "维尔纽斯站", "en": "Vilnius station", "native": "Vilnius"},
        "ヴィルパント駅": {"zh": "维勒潘特站", "en": "Villepinte station", "native": "Villepinte"},
        "ヴッパータール中央駅": {"zh": "伍珀塔尔中央站", "en": "Wuppertal Hauptbahnhof", "native": "Wuppertal Hauptbahnhof"},
        "ヴッパーフェルト駅": {"zh": "伍珀费尔德站", "en": "Wupperfeld station", "native": "Wupperfeld"},
        "龍山駅": {"zh": "龙山站", "en": "Yongsan station", "native": "용산역"},
        "龍陽路駅": {"zh": "龙阳路站", "en": "Longyang Road station", "native": "龙阳路站"},
    },
    "by_vehicle": {
        "Sm5": {"zh": "Sm5型近郊列车", "en": "Sm5 train", "native": "Sm5"},
        "TGV Duplex": {"zh": "TGV Duplex双层高速列车", "en": "TGV Duplex", "native": "TGV Duplex"},
        "アムステルダムトラム「コンビーノ」": {"zh": "阿姆斯特丹有轨电车 Combino", "en": "Amsterdam tram Combino", "native": "Amsterdamse tram Combino"},
        "アムトラック 44型電気式ディーゼル機関車": {"zh": "美铁44型柴电机车", "en": "Amtrak 44 diesel-electric locomotive", "native": "Amtrak 44 diesel-electric locomotive"},
        "アムトラック EMD F40PH「メープルリーフ」": {"zh": "美铁 EMD F40PH Maple Leaf", "en": "Amtrak EMD F40PH Maple Leaf", "native": "Amtrak EMD F40PH Maple Leaf"},
        "イスタンブールトラム ノスタルジック・トラムヴァイ": {"zh": "伊斯坦布尔怀旧有轨电车", "en": "Istanbul nostalgic tram", "native": "Nostaljik Tramvay"},
        "インド鉄道 デカン・オデッセイ・トレイン": {"zh": "印度铁路德干奥德赛列车", "en": "Indian Railways Deccan Odyssey train", "native": "Deccan Odyssey"},
        "オリエント急行": {"zh": "东方快车", "en": "Orient Express", "native": "Orient Express"},
        "ウェスト・コースト鉄道 ウェスト・ハイランド線「ジャコバイト」号": {"zh": "西海岸铁路西高地线 Jacobite 号", "en": "West Coast Railways West Highland line Jacobite", "native": "The Jacobite"},
        "エジプト鉄道 ターボトレイン": {"zh": "埃及铁路涡轮列车", "en": "Egyptian National Railways Turbo Train", "native": "Turbo Train"},
        "キウイレール ミッドランド線 「トランツアルパイン」号": {"zh": "KiwiRail米德兰线 TranzAlpine 号", "en": "KiwiRail Midland Line TranzAlpine", "native": "TranzAlpine"},
        "シーメンス ヴェラロRUS「サプサン」": {"zh": "西门子Velaro RUS Sapsan", "en": "Siemens Velaro RUS Sapsan", "native": "Сапсан"},
        "スイスMOB鉄道 「ゴールデンパス・パノラミック」号": {"zh": "瑞士MOB铁路GoldenPass Panoramic号", "en": "Montreux Oberland Bernois Railway GoldenPass Panoramic", "native": "GoldenPass Panoramic"},
        "スカイライン ドライバーレス・メトロ": {"zh": "檀香山天际线无人驾驶地铁", "en": "Skyline driverless metro", "native": "Skyline driverless metro"},
        "上海トランスラピッド": {"zh": "上海磁浮列车", "en": "Shanghai Maglev Train", "native": "上海磁浮列车"},
        "タイ国有鉄道メークローン線 NKF型気動車": {"zh": "泰国国铁美功线NKF型柴油动车", "en": "State Railway of Thailand Maeklong Line NKF diesel railcar", "native": "NKF diesel railcar"},
        "ダニーデン鉄道 DJ型電気式ディーゼル機関車": {"zh": "达尼丁铁路DJ型柴电机车", "en": "Dunedin Railways DJ class diesel-electric locomotive", "native": "DJ class diesel-electric locomotive"},
        "デリー・メトロ": {"zh": "德里地铁", "en": "Delhi Metro", "native": "Delhi Metro"},
        "トレニタリア E.414「フレッチャビアンカ」": {"zh": "意大利铁路公司E.414 Frecciabianca", "en": "Trenitalia E.414 Frecciabianca", "native": "Frecciabianca"},
        "ドイツ鉄道 燃料電池列車「コラディア・アイリント」": {"zh": "德国铁路Coradia iLint燃料电池列车", "en": "Deutsche Bahn Coradia iLint fuel-cell train", "native": "Coradia iLint"},
        "ドバイ道路交通局 (RTA) ドバイ・トラム シタディス402型": {"zh": "迪拜道路交通局迪拜有轨电车Citadis 402型", "en": "RTA Dubai Tram Citadis 402", "native": "Dubai Tram Citadis 402"},
        "ドバイ道路交通局 (RTA) パーム・ジュメイラ・モノレール": {"zh": "迪拜道路交通局朱美拉棕榈岛单轨", "en": "RTA Palm Jumeirah Monorail", "native": "Palm Jumeirah Monorail"},
        "ハーグ市営交通会社 アヴェニオ": {"zh": "海牙市营交通公司Avenio", "en": "HTM Personenvervoer Avenio", "native": "Avenio"},
        "フェロメックス 「ホセ・クエルボ・エクスプレス」号": {"zh": "墨西哥铁路Jose Cuervo Express号", "en": "Ferromex Jose Cuervo Express", "native": "Jose Cuervo Express"},
        "ベトナム鉄道 D19E型ディーゼル機関車": {"zh": "越南铁路D19E型柴油机车", "en": "Vietnam Railways D19E diesel locomotive", "native": "D19E diesel locomotive"},
        "ペリオン鉄道 A9500系ディーゼル機関車": {"zh": "皮立翁铁路A9500系柴油机车", "en": "Pelion railway A9500 diesel locomotive", "native": "A9500 diesel locomotive"},
        "ペルー・レイル ビスタドーム": {"zh": "秘鲁铁路Vistadome", "en": "PeruRail Vistadome", "native": "Vistadome"},
        "マルセイユ・トラム フレキシティ・アウトルックC": {"zh": "马赛有轨电车Flexity Outlook C", "en": "Marseille tramway Flexity Outlook C", "native": "Flexity Outlook C"},
        "メキシコシティ地下鉄 NM-02型ゴムタイヤ車": {"zh": "墨西哥城地铁NM-02型胶轮车", "en": "Mexico City Metro NM-02 rubber-tyred train", "native": "NM-02"},
        "ラックスレール 寝台列車「ブルートレイン」": {"zh": "勒克斯铁路Blue Train卧铺列车", "en": "Luxrail Blue Train sleeper train", "native": "Blue Train"},
        "リガ交通局 リガ市電 シュコダ15T・15T1/T2/T3": {"zh": "里加交通局里加有轨电车Skoda 15T/15T1/T2/T3", "en": "Rigas satiksme Riga tram Skoda 15T/15T1/T2/T3", "native": "Rīgas satiksme Riga tram Škoda 15T/15T1/T2/T3"},
        "ロッキーマウンテニア鉄道 「ロッキーマウンテニア」号": {"zh": "落基山登山者列车Rocky Mountaineer号", "en": "Rocky Mountaineer train", "native": "Rocky Mountaineer"},
        "ロボスレイル 寝台列車「プライド・オブ・アフリカ」": {"zh": "罗沃斯铁路Pride of Africa卧铺列车", "en": "Rovos Rail Pride of Africa sleeper train", "native": "Pride of Africa"},
        "ヴェルデ・キャニオン鉄道 FP7形ディーゼル機関車": {"zh": "佛得峡谷铁路FP7型柴油机车", "en": "Verde Canyon Railroad FP7 diesel locomotive", "native": "FP7 diesel locomotive"},
        "天津開発区導軌電車 トランスロール": {"zh": "天津开发区导轨电车Translohr", "en": "TEDA Modern Guided Rail Tram Translohr", "native": "Translohr"},
        "セントーサ・エクスプレス": {"zh": "圣淘沙捷运", "en": "Sentosa Express", "native": "Sentosa Express"},
        "シュトースバーン": {"zh": "施图斯缆索铁路", "en": "Stoosbahn", "native": "Stoosbahn"},
        "サンフランシスコ・ケーブルカー": {"zh": "旧金山缆车", "en": "San Francisco cable car", "native": "San Francisco cable car"},
        "カウアイ・プランテーション・レイルウェイ": {"zh": "考艾种植园铁路", "en": "Kauai Plantation Railway", "native": "Kauai Plantation Railway"},
        "クライストチャーチ・トラム": {"zh": "基督城有轨电车", "en": "Christchurch Tramway", "native": "Christchurch Tramway"},
        "シンガポールLRT センカン線 「クリスタルムーバー」": {"zh": "新加坡轻轨盛港线 Crystal Mover", "en": "Singapore LRT Sengkang line Crystal Mover", "native": "Singapore LRT Sengkang line Crystal Mover"},
    },
}

FOREIGN_PREFIX_DISPLAY_TRANSLATIONS = {
    "アムステルダムトラム": {"zh": "阿姆斯特丹有轨电车", "en": "Amsterdam tram", "native": "Amsterdamse tram"},
    "アムトラック": {"zh": "美铁", "en": "Amtrak", "native": "Amtrak"},
    "アラスカ鉄道": {"zh": "阿拉斯加铁路", "en": "Alaska Railroad", "native": "Alaska Railroad"},
    "アレクサンドリア市電": {"zh": "亚历山大有轨电车", "en": "Alexandria tram", "native": "Alexandria tram"},
    "イギリス鉄道": {"zh": "英国铁路", "en": "British railway", "native": "British railway"},
    "イスタンブールトラム": {"zh": "伊斯坦布尔有轨电车", "en": "Istanbul tram", "native": "İstanbul tramvayı"},
    "インド鉄道": {"zh": "印度铁路", "en": "Indian Railways", "native": "Indian Railways"},
    "ウェスト・コースト鉄道": {"zh": "西海岸铁路", "en": "West Coast Railways", "native": "West Coast Railways"},
    "エカテリンブルク市電": {"zh": "叶卡捷琳堡有轨电车", "en": "Yekaterinburg tram", "native": "Екатеринбургский трамвай"},
    "エジプト鉄道": {"zh": "埃及铁路", "en": "Egyptian National Railways", "native": "Egyptian National Railways"},
    "エディンバラ・トラム": {"zh": "爱丁堡有轨电车", "en": "Edinburgh Trams", "native": "Edinburgh Trams"},
    "オランダ鉄道": {"zh": "荷兰铁路", "en": "Nederlandse Spoorwegen", "native": "Nederlandse Spoorwegen"},
    "カイロ地下鉄1号線": {"zh": "开罗地铁1号线", "en": "Cairo Metro Line 1", "native": "Cairo Metro Line 1"},
    "キウイレール": {"zh": "KiwiRail", "en": "KiwiRail", "native": "KiwiRail"},
    "グランドキャニオン鉄道": {"zh": "大峡谷铁路", "en": "Grand Canyon Railway", "native": "Grand Canyon Railway"},
    "グレート・ウェスタン鉄道": {"zh": "大西部铁路", "en": "Great Western Railway", "native": "Great Western Railway"},
    "シンガポールLRT": {"zh": "新加坡轻轨", "en": "Singapore LRT", "native": "Singapore LRT"},
    "シンガポールMRT": {"zh": "新加坡地铁", "en": "Singapore MRT", "native": "Singapore MRT"},
    "シーメンス": {"zh": "西门子", "en": "Siemens", "native": "Siemens"},
    "スイスMOB鉄道": {"zh": "瑞士MOB铁路", "en": "Montreux Oberland Bernois Railway", "native": "Chemin de fer Montreux Oberland bernois"},
    "スカイライン": {"zh": "檀香山天际线", "en": "Skyline", "native": "Skyline"},
    "ソウル交通公社": {"zh": "首尔交通公社", "en": "Seoul Metro", "native": "서울교통공사"},
    "タイ国有鉄道": {"zh": "泰国国家铁路", "en": "State Railway of Thailand", "native": "การรถไฟแห่งประเทศไทย"},
    "ダニーデン鉄道": {"zh": "达尼丁铁路", "en": "Dunedin Railways", "native": "Dunedin Railways"},
    "ダージリン・ヒマラヤ鉄道": {"zh": "大吉岭喜马拉雅铁路", "en": "Darjeeling Himalayan Railway", "native": "Darjeeling Himalayan Railway"},
    "チューリッヒ市交通局": {"zh": "苏黎世市交通局", "en": "Verkehrsbetriebe Zürich", "native": "Verkehrsbetriebe Zürich"},
    "トレニタリア": {"zh": "意大利铁路公司", "en": "Trenitalia", "native": "Trenitalia"},
    "ドイツ鉄道": {"zh": "德国铁路", "en": "Deutsche Bahn", "native": "Deutsche Bahn"},
    "ドバイメトロ": {"zh": "迪拜地铁", "en": "Dubai Metro", "native": "Dubai Metro"},
    "ドバイ道路交通局": {"zh": "迪拜道路交通局", "en": "Roads and Transport Authority", "native": "Roads and Transport Authority"},
    "ニューヨーク市地下鉄": {"zh": "纽约地铁", "en": "New York City Subway", "native": "New York City Subway"},
    "ハウトレイン": {"zh": "豪登列车", "en": "Gautrain", "native": "Gautrain"},
    "ハワイ鉄道": {"zh": "夏威夷铁路", "en": "Hawaiian Railway", "native": "Hawaiian Railway"},
    "ハーグ市営交通会社": {"zh": "海牙市营交通公司", "en": "HTM Personenvervoer", "native": "HTM Personenvervoer"},
    "バイロンベイ鉄道": {"zh": "拜伦湾铁路", "en": "Byron Bay Train", "native": "Byron Bay Train"},
    "バンコク・スカイトレイン": {"zh": "曼谷空铁", "en": "Bangkok Skytrain", "native": "รถไฟฟ้าบีทีเอส"},
    "パシフィック・ナショナル": {"zh": "太平洋国家铁路", "en": "Pacific National", "native": "Pacific National"},
    "パッフィンビリー鉄道": {"zh": "普芬比利铁路", "en": "Puffing Billy Railway", "native": "Puffing Billy Railway"},
    "パリ・メトロ": {"zh": "巴黎地铁", "en": "Paris Métro", "native": "Métro de Paris"},
    "パリ交通公団": {"zh": "巴黎大众运输公司", "en": "RATP", "native": "Régie autonome des transports parisiens"},
    "フェロメックス": {"zh": "墨西哥铁路", "en": "Ferromex", "native": "Ferromex"},
    "フランデレン交通公社": {"zh": "佛兰德交通公司", "en": "De Lijn", "native": "De Lijn"},
    "ブエノスアイレス地下鉄": {"zh": "布宜诺斯艾利斯地铁", "en": "Buenos Aires Underground", "native": "Subte de Buenos Aires"},
    "ブリュッセル首都圏交通": {"zh": "布鲁塞尔首都圈交通", "en": "Brussels Intercommunal Transport Company", "native": "STIB/MIVB"},
    "ヘルシンキ地下鉄": {"zh": "赫尔辛基地铁", "en": "Helsinki Metro", "native": "Helsingin metro"},
    "ベトナム鉄道": {"zh": "越南铁路", "en": "Vietnam Railways", "native": "Đường sắt Việt Nam"},
    "ベルリンSバーン": {"zh": "柏林城市快铁", "en": "Berlin S-Bahn", "native": "S-Bahn Berlin"},
    "ペリオン鉄道": {"zh": "皮立翁铁路", "en": "Pelion railway", "native": "Pelion railway"},
    "ペルー・レイル": {"zh": "秘鲁铁路", "en": "PeruRail", "native": "PeruRail"},
    "ホワイト・パス・アンド・ユーコン・ルート": {"zh": "白隘与育空铁路", "en": "White Pass and Yukon Route", "native": "White Pass and Yukon Route"},
    "マルセイユ・トラム": {"zh": "马赛有轨电车", "en": "Marseille tramway", "native": "Tramway de Marseille"},
    "メキシコシティ・ライトレール": {"zh": "墨西哥城轻轨", "en": "Mexico City Light Rail", "native": "Tren Ligero de la Ciudad de México"},
    "メキシコシティ地下鉄": {"zh": "墨西哥城地铁", "en": "Mexico City Metro", "native": "Metro de la Ciudad de México"},
    "モントルー・オーベルラン・ベルノワ鉄道": {"zh": "蒙特勒-伯尔尼高地铁路", "en": "Montreux Oberland Bernois Railway", "native": "Chemin de fer Montreux Oberland bernois"},
    "ユニオン・ピアソン・エクスプレス": {"zh": "联合车站-皮尔逊机场快线", "en": "Union Pearson Express", "native": "Union Pearson Express"},
    "ラックスレール": {"zh": "勒克斯铁路", "en": "Luxrail", "native": "Luxrail"},
    "リガ交通局": {"zh": "里加交通局", "en": "Rīgas satiksme", "native": "Rīgas satiksme"},
    "リトアニア鉄道": {"zh": "立陶宛铁路", "en": "Lithuanian Railways", "native": "Lietuvos geležinkeliai"},
    "レンフェ": {"zh": "西班牙国家铁路", "en": "Renfe", "native": "Renfe"},
    "レーティッシュ鉄道": {"zh": "雷蒂亚铁路", "en": "Rhaetian Railway", "native": "Rhätische Bahn"},
    "ロシア鉄道": {"zh": "俄罗斯铁路", "en": "Russian Railways", "native": "Российские железные дороги"},
    "ロッキーマウンテニア鉄道": {"zh": "落基山登山者列车", "en": "Rocky Mountaineer", "native": "Rocky Mountaineer"},
    "ロボスレイル": {"zh": "罗沃斯铁路", "en": "Rovos Rail", "native": "Rovos Rail"},
    "ワシントン首都圏交通局": {"zh": "华盛顿都会区交通局", "en": "Washington Metropolitan Area Transit Authority", "native": "Washington Metropolitan Area Transit Authority"},
    "ヴィトーリア・ミナス鉄道": {"zh": "维多利亚-米纳斯铁路", "en": "Vitória-Minas Railway", "native": "Estrada de Ferro Vitória a Minas"},
    "ヴェルデ・キャニオン鉄道": {"zh": "佛得峡谷铁路", "en": "Verde Canyon Railroad", "native": "Verde Canyon Railroad"},
    "ヴッパータール空中鉄道": {"zh": "伍珀塔尔悬挂铁路", "en": "Wuppertal Schwebebahn", "native": "Wuppertaler Schwebebahn"},
    "台湾鉄路公司": {"zh": "台湾铁路公司", "en": "Taiwan Railway Corporation", "native": "臺灣鐵路公司"},
    "天津開発区導軌電車": {"zh": "天津开发区导轨电车", "en": "TEDA Modern Guided Rail Tram", "native": "天津开发区导轨电车"},
    "広島電鉄": {"zh": "广岛电铁", "en": "Hiroshima Electric Railway", "native": "広島電鉄"},
    "水西高速鉄道": {"zh": "水西高速铁路", "en": "Suseo high-speed railway", "native": "수서고속철도"},
    "福井鉄道": {"zh": "福井铁道", "en": "Fukui Railway", "native": "福井鉄道"},
    "秦皇島山海観光鉄道": {"zh": "秦皇岛山海观光铁路", "en": "Qinhuangdao Shanhai Tourist Railway", "native": "秦皇岛山海旅游铁路"},
    "国鉄": {"zh": "国铁", "en": "National railway", "native": "国鉄"},
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


TRANSLATED_DIRECTORY_GROUPS = {"by_foreign_country", "by_operator", "by_line", "by_station", "by_vehicle"}
DOMESTIC_PREFIX_TRANSLATION_EXCLUSIONS = {"広島電鉄", "福井鉄道", "国鉄"}


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
        cleaned = compact_text(item).strip("、。 ")
        if (cleaned.startswith("「") and cleaned.endswith("」")) or (
            cleaned.startswith("『") and cleaned.endswith("』")
        ):
            cleaned = cleaned[1:-1].strip()
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
        part = re.sub(r"\s+ほか$", "", part)
        part = re.sub(r"\s*\(\*\d+\)\s*", "", part)
        part = re.sub(r"\s*座標中心点住所：.*$", "", part)
        part = compact_text(part.strip("、。 "))
        if part.startswith(("（", "(")):
            continue
        if match := re.match(r"^(東京モノレール)\s+", part):
            part = match.group(1)
        if "、" in part:
            comma_parts = [compact_text(item) for item in re.split(r"\s*、\s*", part) if compact_text(item)]
            if all(item.endswith(("新幹線", "本線", "線", "鉄道", "電鉄", "ライン", "号線", "系統")) for item in comma_parts):
                for item in comma_parts:
                    line = cleanup_line_candidate(item)
                    if line:
                        cleaned.append(line)
                continue
        for item in split_compound_line(part):
            item = cleanup_line_candidate(item)
            if item:
                cleaned.append(item)
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


def split_compound_line(value: str) -> list[str]:
    value = compact_text(value)
    if "・" not in value:
        return [value] if value else []
    parts = [part for part in re.split(r"\s*・\s*", value) if part]
    if len(parts) < 2:
        return [value] if value else []
    line_suffixes = ("新幹線", "本線", "線", "鉄道", "電鉄", "ライン", "号線", "Sバーン")
    propagated = []
    if len(parts) >= 2 and (match := re.match(r"^(.+?)\d+号線$", parts[0])):
        prefix = match.group(1)
        for part in parts:
            if re.match(r"^\d+号線$", part):
                propagated.append(f"{prefix}{part}")
            else:
                propagated.append(part)
        parts = propagated
    if all(part.endswith(line_suffixes) for part in parts):
        return parts
    return [value]


def cleanup_station_candidate(value: str) -> str | None:
    value = compact_text(value)
    value = re.sub(r"\s*\(\*\d+\)\s*", "", value)
    if "にある" in value:
        value = value.rsplit("にある", 1)[1]
    value = re.sub(r"^(?:かつてあった|現\s*)", "", value)
    if "駅である" in value:
        value = value.rsplit("駅である", 1)[1]
    if "駅が" in value:
        value = value.rsplit("駅が", 1)[1]
    value = re.sub(r"^[のはがにある]+", "", value)
    value = re.sub(r"^.*の", "", value)
    value = re.sub(r"^(?:[一-龥ぁ-んァ-ヶA-Za-z0-9・ー]+(?:新幹線|本線|線|鉄道|電鉄|ライン))+", "", value)
    if value == "駅":
        return None
    if value in {"最大駅", "最寄り駅", "終着駅", "起点駅", "境界駅", "管轄が分かれる境界駅", "説明で使用されている駅"}:
        return None
    if value.startswith("終着駅"):
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
    value = re.sub(r"\s+ほか$", "", value)
    value = re.sub(r"沿線$", "", value)
    value = re.sub(r"[（(].*$", "", value)
    value = value.strip("（）()")
    value = re.sub(r"鉄道の(?=[一-龥ぁ-んァ-ヶA-Za-z0-9・ー]+線$)", "鉄道", value)
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
    if any(fragment in value for fragment in ["営業廃止", "太陽光発電", "当路線", "保存鉄道", "元ネタ車両も", "株式会社の子会社", "協会の路線", "の線", "のうちの", "駅の軽便鉄道", "呼ばれる線", "元ネタの", "元ネタ車両", "車両は", "駅名としての由来", "運行しているツアー鉄道"]):
        return None
    if value in {"鉄道", "高架鉄道", "路線", "下り線", "保線", "貨物線", "号線", "軽便鉄道", "軽電鉄", "上記鉄道", "南アフリカの旅客鉄道", "南アフリカの鉄道路線", "国内最大の鉄道"}:
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
    if value in OPERATOR_ALIASES:
        return OPERATOR_ALIASES[value]
    value = strip_foreign_region_prefix(value)
    if value in {"JR北海道", "JR東日本", "JR東海", "JR西日本", "JR四国", "JR九州", "JR貨物", "国鉄"}:
        return value
    if re.match(r"^[のはをやと]", value):
        return None
    salvage_patterns = [
        r"ことから(.+)$",
        r"のうちの(.+)$",
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
    if value in {"鉄道", "軽便鉄道", "軽電鉄", "南アフリカの旅客鉄道", "南アフリカの鉄道", "国内最大の鉄道"}:
        return None
    if re.match(r"^(?:の|は|を|や|と|という|上記)", value):
        return None
    if len(value) <= 2:
        return None
    return value


def extract_lines(text: str) -> list[str]:
    if not text:
        return []
    pattern = re.compile(r"([一-龥ぁ-んァ-ヶA-Za-z0-9・ー]+(?:新幹線|本線|線|鉄道|電鉄|ライン|号線|Sバーン)|ハウトレイン)")
    candidates = []
    for item in pattern.findall(text):
        if any(noise in item for noise in ["架線", "延線", "視線", "目線"]):
            continue
        cleaned = cleanup_line_candidate(item)
        if cleaned:
            if "・" in cleaned:
                candidates.extend(split_compound_line(cleaned))
            elif cleaned.count("線") >= 2 and "と" in cleaned:
                candidates.extend(part for part in re.split(r"\s*と\s*", cleaned) if part)
            else:
                candidates.append(cleaned)
    return drop_substring_duplicates(unique_keep_order(candidates))


def extract_vehicles(text: str) -> list[str]:
    if not text:
        return []
    vehicle_prefix = r"(?:[A-ZＡ-Ｚ]{0,4}|キハ|クハネ|クハ|クモハ|モハニ|モハ|雪)"
    patterns = [
        r"([A-ZＡ-Ｚ]{1,4}\d+[A-ZＡ-Ｚ]*(?:-\d+[A-ZＡ-Ｚ]*)?型[一-龥ぁ-んァ-ヶA-Za-z0-9・ー]*機関車)",
        rf"({vehicle_prefix}\s*\d{{2,5}}形(?:\d+番台)?(?:\s*[（(][^）)]*[）)])?)",
        rf"({vehicle_prefix}\s*\d{{2,5}}系(?:\d+番台)?(?:\s*[（(][^）)]*[）)])?)",
        r"(ドクターイエロー)",
        r"(オリエント急行)",
        r"([A-ZＡ-Ｚ]*\s*[A-ZＡ-Ｚ]{2,}\d+[A-ZＡ-Ｚ]*[A-Za-zＡ-Ｚ0-9]*)",
        r"([一-龥ぁ-んァ-ヶA-Za-z0-9・ー]+(?:洗浄車|確認車|延線車|保守用車|検測車|機関車))",
        r"(De\s*Lijn|TEC|MIVB|SNCB|NMBS)",
    ]
    found: list[str] = []
    for pattern in patterns:
        found.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    cleaned = [item for item in (cleanup_vehicle_candidate(value) for value in found) if item]
    return drop_substring_duplicates(unique_keep_order(cleaned))


def cleanup_vehicle_candidate(value: str) -> str | None:
    value = compact_text(value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s+[（(](?:デザイン|設定|双方|前者|後者|.*混同.*).*$", "", value)
    value = re.sub(r"[（(]・[^）)]*[）)]", "", value)
    value = compact_text(value)
    if not value or len(value) <= 1:
        return None
    return value


def normalized_operator_name(value: str) -> str:
    return OPERATOR_ALIASES.get(value, value)


MODEL_VEHICLE_OPERATOR_HINT_RE = re.compile(
    r"(?:鉄道|電鉄|急行|交通(?:局|公社|会社)?|管理局|軌道|モノレール|ライトレール|地下鉄|メトロ|トラム|市電|電車|レール|レイル|LRT|MRT|国鉄|公社|公団|公司|ケーブルカー|スカイトレイン|トランジット|トランスラピッド|トレニタリア|レンフェ|アムトラック|シーメンス|工業|バーン|ルート|エクスプレス)"
)

MODEL_VEHICLE_MARKER_RE = re.compile(
    r"(?:[A-ZＡ-Ｚ]{1,4}[- ]?\d|[A-ZＡ-Ｚ]*\d{1,5}[A-ZＡ-Ｚ]*(?:形|系|型)|\d+t|車両移動機|軌道作業車|機関車|気動車|客車|コンビーノ|トランスロール|アヴェニオ|トランスラピッド|フレキシティ|ヴェラロ|ノスタルジック|クリスタルムーバー|Urbos|EMU|MP40PH|MI09|MI79|「|（)"
)

MODEL_VEHICLE_OPERATOR_EXCLUDES = {
    "オリエント急行",
    "TGV Duplex",
}

MODEL_VEHICLE_OPERATOR_SPECIALS = {
    "愛知こどもの国",
    "パシフィック・ナショナル",
    "ホワイト・パス・アンド・ユーコン・ルート",
    "ユニオン・ピアソン・エクスプレス",
    "セントーサ・エクスプレス",
}


MODEL_OPERATOR_SUFFIXES = [
    "交通局",
    "交通公社",
    "交通会社",
    "鉄道",
    "電鉄",
    "急行",
    "管理局",
    "軌道",
    "モノレール",
    "ライトレール",
    "地下鉄",
    "メトロ",
    "トラム",
    "市電",
    "電車",
    "国鉄",
    "公社",
    "公団",
    "公司",
    "ケーブルカー",
    "スカイトレイン",
    "トランジット",
    "トランスラピッド",
    "トレニタリア",
    "レンフェ",
    "アムトラック",
    "シーメンス",
    "工業",
    "バーン",
    "ルート",
    "エクスプレス",
    "レール",
    "レイル",
]


def candidate_model_operator_names() -> list[str]:
    names = set(MODEL_OPERATOR_NAMES)
    names.update(OPERATOR_ALIASES)
    names.update(OPERATOR_ALIASES.values())
    names.update(OPERATOR_READINGS)
    names.update(LINE_OPERATOR_PREFIXES)
    names.update(LINE_OPERATOR_PREFIXES.values())
    names.update(LINE_PREFIX_READINGS)
    return sorted(names, key=len, reverse=True)


def trim_model_operator_suffix(value: str) -> str:
    if value.startswith("愛知こどもの国 "):
        return "愛知こどもの国"
    for special in ["アムトラック", "シーメンス", "レンフェ", "トレニタリア"]:
        if value == special or value.startswith(f"{special} "):
            return special
    for suffix in MODEL_OPERATOR_SUFFIXES:
        match = re.match(rf"^(.+?{re.escape(suffix)})(?:\s|$)", value)
        if match:
            return match.group(1)
    return value


def cleanup_model_operator_prefix(value: str) -> str | None:
    value = compact_text(value)
    value = re.sub(r"[（(].*$", "", value)
    value = re.sub(r"\s+(?:新塗装|第一建設工業色|東鉄工業色)$", "", value)
    value = trim_model_operator_suffix(value)
    value = value.strip("・/／,，、。:： -")
    value = compact_text(value)
    if not value or value in MODEL_VEHICLE_OPERATOR_EXCLUDES:
        return None
    cleaned = cleanup_operator_candidate(value) or value
    if cleaned in MODEL_VEHICLE_OPERATOR_EXCLUDES:
        return None
    if cleaned in MODEL_VEHICLE_OPERATOR_SPECIALS:
        return normalized_operator_name(cleaned)
    if MODEL_VEHICLE_OPERATOR_HINT_RE.search(cleaned):
        return normalized_operator_name(cleaned)
    return None


def extract_model_vehicle_operators(model_vehicle_raw: str | None) -> list[str]:
    if not model_vehicle_raw:
        return []
    direct = extract_operators(model_vehicle_raw)
    if direct:
        return direct

    raw = compact_text(model_vehicle_raw)
    candidates: list[str] = []
    for name in candidate_model_operator_names():
        if raw.startswith(name):
            candidates.append(normalized_operator_name(name))
            break

    marker = MODEL_VEHICLE_MARKER_RE.search(raw)
    prefix = raw[: marker.start()] if marker else raw
    cleaned_prefix = cleanup_model_operator_prefix(prefix)
    if cleaned_prefix:
        candidates.append(cleaned_prefix)

    if not candidates and MODEL_VEHICLE_OPERATOR_HINT_RE.search(raw):
        cleaned_raw = cleanup_model_operator_prefix(raw)
        if cleaned_raw:
            candidates.append(cleaned_raw)
    return unique_keep_order(candidates)


def vehicle_operator_prefix(model_vehicle_raw: str | None, vehicle: str, model_operators: list[str]) -> str | None:
    if not model_vehicle_raw:
        return model_operators[0] if model_operators else None
    idx = model_vehicle_raw.find(vehicle)
    prefix_text = model_vehicle_raw[:idx] if idx >= 0 else model_vehicle_raw
    candidates = set(model_operators)
    candidates.update(OPERATOR_ALIASES)
    candidates.update(OPERATOR_ALIASES.values())
    candidates.update(OPERATOR_READINGS)
    best: tuple[int, str] | None = None
    for candidate in candidates:
        pos = prefix_text.rfind(candidate)
        if pos >= 0 and (best is None or pos > best[0]):
            best = (pos, normalized_operator_name(candidate))
    if best:
        return best[1]
    return model_operators[0] if model_operators else None


def qualify_vehicles(vehicles: list[str], model_vehicle_raw: str | None, model_operators: list[str]) -> list[str]:
    qualified: list[str] = []
    for vehicle in vehicles:
        if any(operator and operator in vehicle for operator in model_operators):
            qualified.append(vehicle)
            continue
        operator = vehicle_operator_prefix(model_vehicle_raw, vehicle, model_operators)
        for alias, normalized in OPERATOR_ALIASES.items():
            if operator == normalized and vehicle.startswith(alias):
                vehicle = compact_text(vehicle.removeprefix(alias))
                break
        qualified.append(f"{operator} {vehicle}" if operator else vehicle)
    return unique_keep_order(qualified)


def extract_operators(text: str) -> list[str]:
    if not text:
        return []
    patterns = [
        r"(JR北海道|JR東日本|JR東海|JR西日本|JR四国|JR九州|JR貨物)",
        r"(東京メトロ|東急|京急|京王|小田急|東武|西武|近鉄|阪急|南海|西鉄|OsakaMetro|ハピラインふくい)",
        r"([一-龥ぁ-んァ-ヶA-Za-z0-9・ー]+国鉄)",
        r"(国鉄)",
        r"([一-龥ぁ-んァ-ヶA-Za-z0-9・ー]+交通局)",
        r"([一-龥ぁ-んァ-ヶA-Za-z0-9・ー]+鉄道)",
        r"([一-龥ぁ-んァ-ヶA-Za-z0-9・ー]+電鉄)",
        r"(ロボスレイル|ハウトレイン|VRグループ|フェロメックス|メキシコシティ・ライトレール|ベルリンSバーン|キウイレール|バンコク・スカイトレイン|ドバイメトロ|De\s*Lijn|TEC|MIVB|SNCB|NMBS|SNCF)",
    ]
    found: list[str] = []
    for pattern in patterns:
        found.extend(re.findall(pattern, text, flags=re.IGNORECASE))
    cleaned = [item for item in (cleanup_operator_candidate(value) for value in found) if item]
    return drop_substring_duplicates(unique_keep_order(cleaned))


def derive_operators_from_lines(lines: list[str]) -> list[str]:
    operators: list[str] = []
    for line in lines:
        for prefix, operator in LINE_OPERATOR_PREFIXES.items():
            if line.startswith(prefix):
                operators.append(operator)
                break
    return unique_keep_order(operators)


def derive_jr_operators_from_context(lines: list[str], prefectures: list[str], stations: list[str]) -> list[str]:
    operators: list[str] = []
    line_set = set(lines)
    pref_set = set(prefectures)
    station_set = set(stations)
    if "JR中央本線" in line_set:
        if "愛知県" in pref_set or "名古屋市営地下鉄鶴舞線" in line_set:
            operators.append("JR東海")
        elif pref_set & {"東京都", "山梨県", "長野県"}:
            operators.append("JR東日本")
    if "JR東海道本線" in line_set:
        if pref_set & {"東京都", "神奈川県"}:
            operators.append("JR東日本")
        elif pref_set & {"静岡県", "愛知県", "岐阜県"}:
            operators.append("JR東海")
        elif pref_set & {"滋賀県", "京都府", "大阪府", "兵庫県"}:
            operators.append("JR西日本")
    if "JR関西本線" in line_set:
        if pref_set & {"愛知県", "三重県"}:
            operators.append("JR東海")
        elif pref_set & {"京都府", "大阪府", "奈良県", "和歌山県"}:
            operators.append("JR西日本")
    if ("JR大糸線" in line_set or "北陸新幹線" in line_set) and ("糸魚川駅" in station_set or "新潟県" in pref_set):
        operators.append("JR西日本")
    return unique_keep_order(operators)


def normalize_lines_with_context(lines: list[str], model_vehicle_raw: str | None) -> list[str]:
    normalized: list[str] = []
    for line in lines:
        item = line
        if re.match(r"^\d+号線$", item):
            model = model_vehicle_raw or ""
            if "メキシコシティ地下鉄" in model:
                item = f"メキシコシティ地下鉄{item}"
            elif "マルセイユ" in model:
                item = f"マルセイユトラム{item}"
        cleaned = cleanup_line_candidate(item)
        if cleaned:
            normalized.append(cleaned)
    return drop_substring_duplicates(unique_keep_order(normalized))


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
    model_vehicle_operators = extract_model_vehicle_operators(model_vehicle_raw)
    fallback_operators = extract_operators(combined)
    lines = normalize_lines_with_context(extract_lines(combined), model_vehicle_raw)
    vehicles = qualify_vehicles(extract_vehicles(model_vehicle_raw or combined), model_vehicle_raw, model_vehicle_operators)
    stations = extract_stations(name_origin_raw or "")
    absent_station_names = extract_absent_station_names(name_origin_raw or "")
    if model_vehicle_raw and not vehicles:
        vehicles = qualify_vehicles([model_vehicle_raw], model_vehicle_raw, model_vehicle_operators)

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
    display_lines = normalize_lines_with_context(reference_lines or lines, model_vehicle_raw)
    display_stations = reference_stations or stations
    related_operators = unique_keep_order(
        derive_operators_from_lines(display_lines)
        + derive_jr_operators_from_context(display_lines, prefectures, display_stations)
    )
    operators = model_vehicle_operators if model_vehicle_raw else fallback_operators or related_operators
    related_operators = [operator for operator in related_operators if operator not in operators]
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
        "model_vehicle_operators": model_vehicle_operators,
        "related_operators": related_operators,
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


INFERRED_STATION_READINGS: dict[str, str] = {}


def denko_name_stem(name: str) -> str:
    match = re.match(r"[一-龥々ヶ]+", name or "")
    return match.group(0) if match else ""


def infer_station_readings(records: list[dict[str, Any]]) -> None:
    inferred: dict[str, str] = {}
    for record in records:
        raw = record.get("name_origin_raw") or ""
        match = re.search(r"苗字は[「『]([^」』]+)[」』]と読み", raw)
        if not match:
            continue
        reading = katakana_to_hiragana(compact_text(match.group(1)))
        stem = denko_name_stem(record.get("name") or "")
        if not reading or not stem:
            continue
        for station in record.get("prototype_stations") or []:
            station_base = re.sub(r"\s*[（(].*$", "", station).removesuffix("駅")
            if station_base and (station_base.startswith(stem) or stem.startswith(station_base)):
                inferred.setdefault(station, f"{reading}えき")
    INFERRED_STATION_READINGS.clear()
    INFERRED_STATION_READINGS.update(inferred)


def station_reading(key: str) -> str | None:
    return STATION_READINGS.get(key) or INFERRED_STATION_READINGS.get(key)


def prefixed_reading(key: str) -> str | None:
    candidates: list[tuple[str, str]] = []
    candidates.extend((name, reading) for name, reading in OPERATOR_READINGS.items())
    candidates.extend((name, reading) for name, reading in LINE_PREFIX_READINGS.items())
    candidates.extend((name, reading) for name, reading in LINE_READINGS.items())
    candidates.extend((name, reading) for name, reading in STATION_READINGS.items())
    candidates.extend((name, reading) for name, reading in INFERRED_STATION_READINGS.items())
    for name, reading in sorted(candidates, key=lambda item: len(item[0]), reverse=True):
        if key.startswith(name):
            suffix = key.removeprefix(name).strip()
            return f"{reading} {suffix}" if suffix else reading
    return None


def line_reading(key: str) -> str | None:
    if key in LINE_READINGS:
        return LINE_READINGS[key]
    if key in OPERATOR_READINGS:
        return OPERATOR_READINGS[key]
    for name, reading in LINE_PREFIX_READINGS.items():
        if key.startswith(name):
            return reading
    for name, reading in OPERATOR_READINGS.items():
        if key.startswith(name):
            return reading
    return None


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
    elif group == "by_line":
        if reading := line_reading(key):
            aliases.append(reading)
    elif group == "by_station":
        if reading := station_reading(key):
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


def translated_display(group: str, key: str) -> dict[str, str] | None:
    if group not in TRANSLATED_DIRECTORY_GROUPS:
        return None
    exact = FOREIGN_DISPLAY_TRANSLATIONS.get(group, {}).get(key)
    if exact:
        return {"ja": key, **exact}
    if group not in {"by_operator", "by_line", "by_vehicle"}:
        return None
    for prefix, base in sorted(FOREIGN_PREFIX_DISPLAY_TRANSLATIONS.items(), key=lambda item: len(item[0]), reverse=True):
        if prefix in DOMESTIC_PREFIX_TRANSLATION_EXCLUSIONS:
            continue
        if not key.startswith(prefix):
            continue
        suffix = key.removeprefix(prefix).strip()
        if suffix:
            return {
                "ja": key,
                "zh": f"{base['zh']} {suffix}",
                "en": f"{base['en']} {suffix}",
                "native": f"{base['native']} {suffix}",
            }
        return {"ja": key, **base}
    return None


def translation_search_aliases(group: str, key: str) -> list[str]:
    translation = translated_display(group, key)
    if not translation:
        return []
    aliases = [
        translation.get("zh", ""),
        translation.get("en", ""),
        translation.get("native", ""),
        translation.get("ja", ""),
    ]
    return unique_keep_order([alias for alias in aliases if alias])


def romanized_sort_text(text: str) -> str:
    text = compact_text(text)
    if unidecode:
        text = unidecode(text)
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", ascii_text).strip().casefold()


def romanized_initial(text: str) -> str:
    normalized = romanized_sort_text(text)
    match = re.search(r"[a-z]", normalized)
    return match.group(0).upper() if match else "#"


def directory_primary_reading(group: str, key: str) -> str:
    if group == "by_prefecture":
        return PREFECTURE_READINGS.get(key) or key
    if group == "by_operator":
        if key in OPERATOR_READINGS:
            return OPERATOR_READINGS[key]
        for name, reading in OPERATOR_READINGS.items():
            if name in key:
                return reading
    if group == "by_line":
        if reading := line_reading(key):
            return reading
    if group == "by_station":
        return station_reading(key) or key
    if group == "by_vehicle":
        if reading := prefixed_reading(key):
            return reading
    if group == "by_voice_actor":
        return VOICE_ACTOR_READINGS.get(key) or key
    return key


def directory_search_key(group: str, key: str) -> str:
    parts = [key, *reading_aliases(group, key), *translation_search_aliases(group, key)]
    return normalized_search_text(" ".join(parts))


def directory_section_label(group: str, key: str) -> str:
    if group == "by_birthday":
        month, _, _ = birthday_sort_key(key)
        return f"{month}月" if month != 99 else "#"
    if translation := translated_display(group, key):
        zh = compact_text(translation.get("zh", ""))
        if zh:
            return romanized_initial(zh)
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
        ("あ", "あいうえおアイウエオヴ"),
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
    if translation := translated_display(group, key):
        zh = compact_text(translation.get("zh", ""))
        return (2, romanized_initial(zh), romanized_sort_text(zh), zh, key)
    sort_text = directory_primary_reading(group, key)
    initial = kana_initial(sort_text)
    directory_groups = {"by_operator", "by_line", "by_voice_actor", "by_station", "by_vehicle", "by_absent_station_name"}
    if group in directory_groups and len(initial) == 1 and initial.isascii() and initial.isalpha():
        return (2, initial, romanized_sort_text(sort_text), key)
    order = ["あ", "か", "さ", "た", "な", "は", "ま", "や", "ら", "わ", "漢", "#"]
    if group in directory_groups:
        order = ["あ", "か", "さ", "た", "な", "は", "ま", "や", "ら", "わ", "#", "漢"]
    rank = order.index(initial) if initial in order else 20
    return (1, rank, initial, sort_text, key)


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


def denko_ref(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "denko_id": record["denko_id"],
        "detail_url": record["detail_url"],
        "name": record["name"],
        "href": f"#{denko_anchor(record['denko_id'])}",
        "countries": record.get("prototype_countries") or [],
    }


def add_index_entry(index: dict[str, dict[str, list[dict[str, Any]]]], group: str, key: str, record: dict[str, Any]) -> None:
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


def translated_meta_text(group: str, translation: dict[str, str]) -> str:
    if group == "by_foreign_country":
        return translation.get("ja", "")
    parts = []
    en = compact_text(translation.get("en", ""))
    native = translation.get("native")
    if native and native != en:
        parts.append(f"原文: {native}")
    elif en:
        parts.append(f"英语: {en}")
    if ja := translation.get("ja"):
        parts.append(f"日文: {ja}")
    return " · ".join(parts)


def country_display_name(country: str) -> str:
    translation = translated_display("by_foreign_country", country)
    return translation["zh"] if translation else country


def directory_country_note(group: str, refs: list[dict[str, Any]]) -> str:
    if group not in {"by_operator", "by_line", "by_station", "by_vehicle"}:
        return ""
    countries = unique_keep_order(
        country_display_name(country)
        for ref in refs
        for country in (ref.get("countries") or [])
        if country
    )
    if not countries:
        return ""
    return "、".join(countries)


def render_country_note(note: str) -> str:
    return f"""<span class="country-note">{esc(note)}</span>""" if note else ""


def render_translated_key(group: str, key: str, multi: str = "", country_note: str = "") -> str:
    country_html = render_country_note(country_note)
    translation = translated_display(group, key)
    if not translation:
        return f"""{esc(key)}{multi}{country_html}"""
    return f"""<span class="translated-key">
      <span><span class="translated-key-main">{esc(translation['zh'])}</span>{multi}{country_html}</span>
      <span class="translated-key-meta">{esc(translated_meta_text(group, translation))}</span>
    </span>"""


def render_translated_value_list(group: str, values: list[str]) -> str:
    if not values:
        return "-"
    items = []
    for value in values:
        translation = translated_display(group, value)
        if translation:
            items.append(
                f"""<span class="translated-inline"><span class="translated-inline-main">{esc(translation['zh'])}</span><span class="translated-inline-meta">{esc(translated_meta_text(group, translation))}</span></span>"""
            )
        else:
            items.append(f"""<span class="plain-inline">{esc(value)}</span>""")
    return """<span class="value-list">""" + "".join(items) + "</span>"


def render_directory_group(group: str, title: str, entries: dict[str, list[dict[str, Any]]], empty_text: str = "暂无") -> str:
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
        item_id = directory_anchor_id(group, key)
        if initial != last_initial:
            header_id = directory_anchor_id(group, f"section:{initial}")
            quick_links.append(f"""<button type="button" data-directory-section="{esc(item_id)}">{esc(initial)}</button>""")
            items.append(f"""<li class="directory-section" id="{esc(header_id)}">{esc(initial)}</li>""")
            last_initial = initial
        links = " ".join(
            f"""<span class="denko-chip"><a href="{esc(ref['href'])}">{esc(ref['denko_id'])} {esc(ref['name'])}</a></span>"""
            for ref in refs
        )
        multi = f"""<span class="entry-count">{len(refs)}件</span>""" if len(refs) > 1 else ""
        country_note = directory_country_note(group, refs)
        search_key = directory_search_key(group, key)
        items.append(
            f"""<li id="{esc(item_id)}" data-directory-item data-key="{esc(search_key)}"><span class="directory-key">{render_translated_key(group, key, multi, country_note)}</span><span class="directory-links">{links}</span></li>"""
        )
    quick = f"""<nav class="directory-quick" aria-label="{esc(title)} 快速选择">{''.join(quick_links)}</nav>"""
    count_html = "" if group in {"by_birthday", "by_prefecture", "by_foreign_country"} else f" <span>{len(entries)}</span>"
    return f"""<section class="directory-card">
      <h2>{esc(title)}{count_html}</h2>
      <div class="directory-tools">
        <input type="search" placeholder="搜索后跳转" aria-label="{esc(title)} 搜索" data-directory-search>
        <button type="button" data-directory-jump>跳转</button>
      </div>
      {quick}
      <ul class="directory-list">{''.join(items)}</ul>
      <div class="directory-footer"><button type="button" data-directory-expand aria-pressed="false">展开</button></div>
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
    infer_station_readings(records)
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
        related_operator_html = (
            f"""<div><dt>关联公司</dt><dd>{render_translated_value_list('by_operator', record.get('related_operators') or [])}</dd></div>"""
            if record.get("related_operators")
            else ""
        )
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
        <div><dt>国家/地区</dt><dd>{render_translated_value_list('by_foreign_country', record.get('prototype_countries') or [])}</dd></div>
        <div><dt>公司/运营者</dt><dd>{render_translated_value_list('by_operator', record.get('prototype_operators') or [])}</dd></div>
        {related_operator_html}
        <div><dt>车辆候选</dt><dd>{render_translated_value_list('by_vehicle', record['prototype_vehicles'])}</dd></div>
        <div><dt>线路候选</dt><dd>{render_translated_value_list('by_line', record['prototype_lines'])}</dd></div>
        <div><dt>站点候选</dt><dd>{render_translated_value_list('by_station', record['prototype_stations'])}</dd></div>
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
    .directory-quick button {{ min-width:22px; text-align:center; border:1px solid #d0d7de; border-radius:4px; padding:1px 4px; color:#57606a; background:#fff; font:inherit; font-size:11px; font-weight:600; cursor:pointer; }}
    .directory-quick button:hover {{ background:#f6f8fa; color:#0969da; }}
    .directory-card ul {{ list-style:none; padding:0; margin:0; display:grid; gap:7px; }}
    .directory-list {{ position:relative; max-height:520px; overflow:auto; overscroll-behavior:contain; padding-right:4px; scrollbar-gutter:stable; }}
    .directory-card.is-expanded .directory-list {{ max-height:min(72vh, 900px); }}
    .directory-footer {{ position:sticky; bottom:0; z-index:3; display:flex; justify-content:center; align-items:center; margin:6px -10px -10px; padding:6px 10px 8px; background:linear-gradient(rgba(255,255,255,0), #fff 35%); border-bottom:1px solid #eef1f4; }}
    .directory-footer button {{ min-width:72px; border:1px solid #d0d7de; border-radius:999px; background:#f6f8fa; color:#57606a; padding:2px 12px; font:inherit; font-size:11px; font-weight:700; cursor:pointer; line-height:1.4; box-shadow:0 1px 2px rgba(31,35,40,.05); }}
    .directory-footer button:hover {{ background:#eef6ff; border-color:#8cbeef; color:#0969da; }}
    .directory-card li {{ display:grid; gap:3px; }}
    .directory-section {{ position:sticky; top:0; z-index:1; margin-top:2px; padding:2px 0; background:#fff; color:#68707c; font-size:11px; font-weight:700; border-bottom:1px solid #eef1f4; }}
    .directory-hit {{ outline:2px solid #f2cc60; outline-offset:2px; border-radius:4px; background:#fff8c5; }}
    .directory-key {{ font-weight:600; }}
    .translated-key {{ display:grid; gap:2px; }}
    .translated-key-main {{ font-weight:700; }}
    .translated-key-meta {{ color:#68707c; font-size:11px; font-weight:500; line-height:1.35; }}
    .country-note {{ display:inline-flex; align-items:center; margin-left:6px; border:1px solid #d8dee4; border-radius:999px; padding:1px 6px; color:#57606a; background:#f6f8fa; font-size:11px; font-weight:600; vertical-align:1px; }}
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
    .value-list {{ display:flex; flex-direction:column; gap:5px; }}
    .translated-inline, .plain-inline {{ display:inline-grid; gap:1px; align-items:start; }}
    .translated-inline-main {{ font-weight:650; }}
    .translated-inline-meta {{ color:#68707c; font-size:11px; line-height:1.35; }}
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
        let current = 0;
        let node = target;
        while (node && node !== list) {{
          current += node.offsetTop || 0;
          node = node.offsetParent;
        }}
        if (node !== list) {{
          current = list.scrollTop + target.getBoundingClientRect().top - list.getBoundingClientRect().top;
        }}
        let offset = block === 'center' ? (list.clientHeight - target.offsetHeight) / 2 : 0;
        if (block === 'start') {{
          const section = target.previousElementSibling?.classList.contains('directory-section')
            ? target.previousElementSibling
            : null;
          offset = section ? section.offsetHeight + 6 : 8;
        }}
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
        const expandButton = card.querySelector('[data-directory-expand]');
        const input = card.querySelector('[data-directory-search]');
        if (button) button.addEventListener('click', () => jumpInCard(card));
        if (expandButton) expandButton.addEventListener('click', () => {{
          const expanded = card.classList.toggle('is-expanded');
          expandButton.textContent = expanded ? '收起' : '展开';
          expandButton.setAttribute('aria-pressed', expanded ? 'true' : 'false');
        }});
        if (input) input.addEventListener('keydown', (event) => {{
          if (event.key === 'Enter') {{
            event.preventDefault();
            jumpInCard(card);
          }}
        }});
      }});
      document.querySelectorAll('.directory-quick [data-directory-section]').forEach((button) => {{
        button.addEventListener('click', (event) => {{
          const id = button.dataset.directorySection;
          if (!id) return;
          const target = document.getElementById(id);
          const list = button.closest('.directory-card')?.querySelector('.directory-list');
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


def strip_trailing_html_whitespace(html_text: str) -> str:
    return "\n".join(line.rstrip() for line in html_text.splitlines()) + "\n"


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
    parser.add_argument("--render-only", action="store_true", help="Render HTML/index from the existing prototype JSONL without reparsing wiki caches.")
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
    if args.render_only:
        records = read_jsonl(out_jsonl)
        infer_station_readings(records)
        out_index_json.write_text(json.dumps(build_index(records, source_records_path=out_jsonl), ensure_ascii=False, indent=2), encoding="utf-8")
        out_html.parent.mkdir(parents=True, exist_ok=True)
        out_html.write_text(strip_trailing_html_whitespace(render_html(records, dataset_label, source_records_path=out_jsonl)), encoding="utf-8")
        summary = {
            "html": str(out_html.relative_to(ROOT)),
            "index_json": str(out_index_json.relative_to(ROOT)),
            "jsonl": str(out_jsonl.relative_to(ROOT)),
            "records": len(records),
            "prompt_errors": prompt_error_items(records),
            "render_only": True,
        }
        print(json.dumps(summary, ensure_ascii=False))
        return
    reference_lookup = build_reference_lookup({row["identity"]["name"] for row in denko_rows})
    birthday_profile_lookup = parse_birthday_profile_reference(BIRTHDAY_PROFILE_PAGE)
    state = load_state()
    records: list[dict[str, Any]] = []
    for denko_id in selected_ids:
        row = by_id[denko_id]
        html_text, cache_meta = fetch_html(denko_id, row["identity"]["detail_url"], state, refresh=args.refresh)
        records.append(build_record(row, html_text, cache_meta, reference_lookup, birthday_profile_lookup))
    infer_station_readings(records)
    write_jsonl(out_jsonl, records)
    out_index_json.write_text(json.dumps(build_index(records, source_records_path=out_jsonl), ensure_ascii=False, indent=2), encoding="utf-8")
    out_html.parent.mkdir(parents=True, exist_ok=True)
    out_html.write_text(strip_trailing_html_whitespace(render_html(records, dataset_label, source_records_path=out_jsonl)), encoding="utf-8")
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
