#!/usr/bin/env python3

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path


BASE = Path(__file__).resolve().parent

SRC = (
    BASE.parent
    / "src"
    / "main"
    / "assets"
    / "cards_union.js"
)

NAME_FILE = (
    BASE
    / "union_ja_names.json"
)

ID_FILE = (
    BASE
    / "union_ja_ids.json"
)

SET_FILE = (
    BASE
    / "union_ja_set_map.json"
)


# ============================================
# 設定
# ============================================

# 1回で処理するカード数
BATCH_SIZE = 200

# アクセス間隔
WAIT = 0.35

# タイムアウト
TIMEOUT = 20

# 日本版商品番号を探す範囲
UA_MIN = 1
UA_MAX = 80


BAD_NAMES = {
    "おすすめデッキ",
    "カードリスト",
    "商品情報",
    "収録商品",
    "カード画像",
    "ユニオンアリーナ｜UNION ARENA",
    "ユニオンアリーナ",
    "UNION ARENA",
}


# ============================================
# JSON
# ============================================

def load_json(path):

    if not path.exists():
        return {}

    try:
        data = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(data, dict):
            return data

    except Exception as error:

        print(
            "JSON load error:",
            path,
            error
        )

    return {}


def save_json(
    path,
    data
):

    path.write_text(
        json.dumps(
            dict(
                sorted(
                    data.items()
                )
            ),
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


# ============================================
# 英語版カード一覧
# ============================================

def load_cards():

    text = SRC.read_text(
        encoding="utf-8"
    )

    marker = (
        "window.TCG_CARD_DATA.union="
    )

    pos = text.find(
        marker
    )

    if pos < 0:

        raise RuntimeError(
            "Union data not found"
        )

    raw = text[
        pos + len(marker):
    ].strip()

    if raw.endswith(";"):
        raw = raw[:-1]

    data = json.loads(
        raw
    )

    if not isinstance(
        data,
        list
    ):

        raise RuntimeError(
            "Union data invalid"
        )

    result = []

    seen = set()

    for card in data:

        if not isinstance(
            card,
            dict
        ):
            continue

        card_id = str(
            card.get(
                "id",
                ""
            )
        ).strip()

        if (
            not card_id
            or
            card_id in seen
        ):
            continue

        seen.add(
            card_id
        )

        result.append(
            card_id
        )

    return result


# ============================================
# カード番号解析
#
# UE03BT/JJK-1-001
# ↓
# prefix = UE03BT/JJK
# title  = JJK
# kind   = BT
# suffix = 1-001
# ============================================

def parse_card_id(
    card_id
):

    match = re.match(
        r"^(UE|UA)"
        r"(\d+)"
        r"(BT|ST)"
        r"/"
        r"([A-Z0-9]+)"
        r"-(.+)$",
        card_id,
        flags=re.I
    )

    if not match:
        return None

    return {
        "region":
            match.group(1).upper(),

        "number":
            int(
                match.group(2)
            ),

        "kind":
            match.group(3).upper(),

        "title":
            match.group(4).upper(),

        "suffix":
            match.group(5),

        "prefix":
            (
                match.group(1).upper()
                + match.group(2)
                + match.group(3).upper()
                + "/"
                + match.group(4).upper()
            )
    }


# ============================================
# 日本語判定
# ============================================

def contains_japanese(
    value
):

    return bool(
        re.search(
            r"[\u3040-\u30ff\u3400-\u9fff]",
            str(value)
        )
    )


def valid_name(
    name
):

    name = str(
        name or ""
    ).strip()

    if not name:
        return False

    if name in BAD_NAMES:
        return False

    if (
        "UNION ARENA"
        in name.upper()
    ):
        return False

    return contains_japanese(
        name
    )


# ============================================
# HTML取得
# ============================================

def fetch_html(
    japanese_id
):

    encoded = (
        urllib.parse.quote(
            japanese_id,
            safe=""
        )
    )

    url = (
        "https://www.unionarena-tcg.com/"
        "jp/cardlist/detail_iframe.php"
        "?card_no="
        + encoded
    )

    req = (
        urllib.request.Request(
            url,
            headers={
                "User-Agent":
                    "Mozilla/5.0",

                "Accept":
                    "text/html",

                "Accept-Language":
                    "ja-JP,ja;q=0.9",
            }
        )
    )

    with urllib.request.urlopen(
        req,
        timeout=TIMEOUT
    ) as response:

        return (
            response
            .read()
            .decode(
                "utf-8",
                errors="replace"
            )
        )


# ============================================
# HTML整理
# ============================================

def clean(
    text
):

    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    replacements = {
        "&amp;": "&",
        "&quot;": '"',
        "&#39;": "'",
        "&nbsp;": " ",
        "&lt;": "<",
        "&gt;": ">",
    }

    for before, after in (
        replacements.items()
    ):

        text = text.replace(
            before,
            after
        )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


# ============================================
# カード名取得
#
# これはテストで
#
# UA02BT/JJK-1-001
# → 虎杖 悠仁
#
# が取れた方法
# ============================================

def extract_name(
    html,
    japanese_id
):

    pattern = (
        r'alt=["\']'
        + re.escape(
            japanese_id
        )
        + r'\s+([^"\']+)'
        + r'["\']'
    )

    match = re.search(
        pattern,
        html,
        flags=re.I
    )

    if match:

        name = clean(
            match.group(1)
        )

        if valid_name(
            name
        ):
            return name

    return ""


# ============================================
# 日本語カード確認
# ============================================

def get_japanese_name(
    japanese_id
):

    try:

        html = fetch_html(
            japanese_id
        )

        return extract_name(
            html,
            japanese_id
        )

    except Exception as error:

        print(
            "fetch error:",
            japanese_id,
            error
        )

        return ""


# ============================================
# 日本版商品番号を自動探索
#
# 例：
#
# UE03BT/JJK
#
# について
#
# UA01BT/JJK
# UA02BT/JJK
# UA03BT/JJK
# ...
#
# を順番に確認。
#
# UA02BT/JJK が見つかったら
# 以降はキャッシュして再探索しない。
# ============================================

def discover_japanese_prefix(
    info,
    set_map
):

    english_prefix = (
        info["prefix"]
    )

    cached = set_map.get(
        english_prefix
    )

    if cached:
        return cached

    print("")
    print(
        "Searching Japanese set:",
        english_prefix
    )

    kind = info["kind"]
    title = info["title"]
    suffix = info["suffix"]

    # まず英語版番号付近を優先
    original_number = (
        info["number"]
    )

    candidates = []

    for offset in range(
        -5,
        6
    ):

        number = (
            original_number
            + offset
        )

        if (
            UA_MIN
            <= number
            <= UA_MAX
        ):

            candidates.append(
                number
            )

    # 残り全部
    for number in range(
        UA_MIN,
        UA_MAX + 1
    ):

        if number not in candidates:
            candidates.append(
                number
            )

    for number in candidates:

        japanese_prefix = (
            f"UA{number:02d}"
            f"{kind}/"
            f"{title}"
        )

        japanese_id = (
            japanese_prefix
            + "-"
            + suffix
        )

        name = (
            get_japanese_name(
                japanese_id
            )
        )

        if valid_name(
            name
        ):

            print(
                "FOUND SET:",
                english_prefix,
                "->",
                japanese_prefix
            )

            print(
                japanese_id,
                "->",
                name
            )

            set_map[
                english_prefix
            ] = japanese_prefix

            save_json(
                SET_FILE,
                set_map
            )

            return japanese_prefix

        time.sleep(
            WAIT
        )

    print(
        "SET NOT FOUND:",
        english_prefix
    )

    return ""


# ============================================
# 英語ID → 日本ID
# ============================================

def convert_to_japanese_id(
    english_id,
    set_map
):

    info = parse_card_id(
        english_id
    )

    if not info:
        return ""

    japanese_prefix = (
        discover_japanese_prefix(
            info,
            set_map
        )
    )

    if not japanese_prefix:
        return ""

    return (
        japanese_prefix
        + "-"
        + info["suffix"]
    )


# ============================================
# 誤取得データ除去
# ============================================

def clean_existing_names(
    names
):

    result = {}

    for key, value in (
        names.items()
    ):

        key = str(
            key
        ).strip()

        value = str(
            value
        ).strip()

        if (
            key
            and
            valid_name(
                value
            )
        ):

            result[
                key
            ] = value

    return result


# ============================================
# メイン
# ============================================

def main():

    cards = load_cards()

    names = clean_existing_names(
        load_json(
            NAME_FILE
        )
    )

    japanese_ids = load_json(
        ID_FILE
    )

    set_map = load_json(
        SET_FILE
    )

    print(
        "Union cards:",
        len(cards)
    )

    print(
        "Valid Japanese names:",
        len(names)
    )

    print(
        "Japanese ID mappings:",
        len(japanese_ids)
    )

    print(
        "Set mappings:",
        len(set_map)
    )

    remaining = [
        card_id
        for card_id in cards
        if card_id not in names
    ]

    print(
        "Remaining:",
        len(remaining)
    )

    batch = (
        remaining[
            :BATCH_SIZE
        ]
    )

    success = 0
    failed = 0

    for index, english_id in (
        enumerate(
            batch,
            start=1
        )
    ):

        print("")
        print(
            f"[{index}/"
            f"{len(batch)}]"
        )

        print(
            "EN:",
            english_id
        )

        japanese_id = (
            japanese_ids.get(
                english_id,
                ""
            )
        )

        if not japanese_id:

            japanese_id = (
                convert_to_japanese_id(
                    english_id,
                    set_map
                )
            )

        if not japanese_id:

            failed += 1

            print(
                "JP ID: NOT FOUND"
            )

            continue

        name = (
            get_japanese_name(
                japanese_id
            )
        )

        if valid_name(
            name
        ):

            names[
                english_id
            ] = name

            japanese_ids[
                english_id
            ] = japanese_id

            success += 1

            print(
                "JP:",
                japanese_id
            )

            print(
                "NAME:",
                name
            )

        else:

            failed += 1

            print(
                "JP:",
                japanese_id
            )

            print(
                "NAME: NOT FOUND"
            )

        # 10件ごと保存
        if index % 10 == 0:

            save_json(
                NAME_FILE,
                names
            )

            save_json(
                ID_FILE,
                japanese_ids
            )

            save_json(
                SET_FILE,
                set_map
            )

            print(
                "Intermediate save"
            )

        time.sleep(
            WAIT
        )

    # 最終保存
    save_json(
        NAME_FILE,
        names
    )

    save_json(
        ID_FILE,
        japanese_ids
    )

    save_json(
        SET_FILE,
        set_map
    )

    print("")
    print(
        "========================"
    )

    print(
        "Batch complete"
    )

    print(
        "Success:",
        success
    )

    print(
        "Failed:",
        failed
    )

    print(
        "Japanese names:",
        len(names)
    )

    print(
        "Japanese IDs:",
        len(japanese_ids)
    )

    print(
        "Set mappings:",
        len(set_map)
    )

    print(
        "Remaining:",
        len(cards) - len(names)
    )

    print(
        "========================"
    )


if __name__ == "__main__":
    main()
