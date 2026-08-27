#!/usr/bin/env python3

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = BASE.parent / "src/main/assets/cards_union.js"
OUT = BASE / "union_ja_names.json"

BATCH = 300
WAIT = 0.4
TIMEOUT = 15


def load_ids():

    text = SRC.read_text(
        encoding="utf-8"
    )

    marker = (
        "window.TCG_CARD_DATA.union="
    )

    p = text.find(marker)

    if p < 0:
        raise RuntimeError(
            "Union data not found"
        )

    raw = text[
        p + len(marker):
    ].strip()

    if raw.endswith(";"):
        raw = raw[:-1]

    cards = json.loads(raw)

    ids = []
    seen = set()

    for card in cards:

        cid = str(
            card.get("id", "")
        ).strip()

        if (
            cid
            and cid not in seen
        ):
            seen.add(cid)
            ids.append(cid)

    return ids


def load_map():

    if not OUT.exists():
        return {}

    try:

        data = json.loads(
            OUT.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(data, dict):

            # 前回の誤取得データを除去
            return {
                str(k).strip():
                str(v).strip()

                for k, v in data.items()

                if str(k).strip()
                and str(v).strip()
                and str(v).strip()
                not in {
                    "おすすめデッキ",
                    "カードリスト",
                    "商品情報",
                    "Q&A",
                    "収録商品"
                }
            }

    except Exception as e:

        print(
            "map load error:",
            e
        )

    return {}


def save_map(data):

    OUT.write_text(
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

    print(
        "saved:",
        len(data)
    )


def clean(text):

    text = re.sub(
        r"<script.*?</script>",
        "",
        text,
        flags=re.I | re.S
    )

    text = re.sub(
        r"<style.*?</style>",
        "",
        text,
        flags=re.I | re.S
    )

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
        "&gt;": ">"
    }

    for a, b in replacements.items():
        text = text.replace(
            a,
            b
        )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def contains_japanese(text):

    return bool(
        re.search(
            r"[\u3040-\u30ff\u3400-\u9fff]",
            text
        )
    )


def fetch_html(card_id):

    encoded = urllib.parse.quote(
        card_id,
        safe=""
    )

    url = (
        "https://www.unionarena-tcg.com/"
        "jp/cardlist/detail_iframe.php"
        f"?card_no={encoded}"
    )

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "Mozilla/5.0",

            "Accept":
                "text/html",

            "Accept-Language":
                "ja-JP,ja;q=0.9"
        }
    )

    with urllib.request.urlopen(
        req,
        timeout=TIMEOUT
    ) as response:

        return response.read().decode(
            "utf-8",
            errors="replace"
        )


def name_from_image_alt(
    html,
    card_id
):

    patterns = [

        r'alt=["\']'
        + re.escape(card_id)
        + r'\s+([^"\']+)["\']',

        r'alt=["\'][^"\']*'
        + re.escape(card_id)
        + r'\s+([^"\']+)["\']'
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            flags=re.I
        )

        if not match:
            continue

        name = clean(
            match.group(1)
        )

        if (
            name
            and
            name != card_id
            and
            contains_japanese(name)
        ):
            return name

    return ""


def name_from_heading(
    html
):

    headings = re.findall(
        r"<h[1-3][^>]*>(.*?)</h[1-3]>",
        html,
        flags=re.I | re.S
    )

    blacklist = {
        "おすすめデッキ",
        "カードリスト",
        "商品情報",
        "収録商品",
        "Q&A",
        "カード画像"
    }

    for raw in headings:

        text = clean(raw)

        if not text:
            continue

        if text in blacklist:
            continue

        if not contains_japanese(text):
            continue

        # 「虎杖 悠仁 いたどり ゆうじ」
        # のような場合、ふりがなを可能な範囲で除去
        parts = text.split()

        if len(parts) >= 3:

            kanji_parts = []

            for part in parts:

                if re.search(
                    r"[\u3400-\u9fff]",
                    part
                ):
                    kanji_parts.append(
                        part
                    )

                elif kanji_parts:
                    break

            if kanji_parts:

                candidate = " ".join(
                    kanji_parts
                ).strip()

                if candidate:
                    return candidate

        return text

    return ""


def fetch_name(card_id):

    html = fetch_html(
        card_id
    )

    # 画像altはカード番号とカード名が
    # セットで入るので最優先
    name = name_from_image_alt(
        html,
        card_id
    )

    if name:
        return name

    # 見出しから取得
    name = name_from_heading(
        html
    )

    if name:
        return name

    return ""


def valid_name(name):

    if not name:
        return False

    blacklist = {
        "おすすめデッキ",
        "カードリスト",
        "商品情報",
        "収録商品",
        "Q&A",
        "カード画像"
    }

    if name in blacklist:
        return False

    return contains_japanese(
        name
    )


def main():

    ids = load_ids()

    names = load_map()

    print(
        "total:",
        len(ids)
    )

    print(
        "valid existing:",
        len(names)
    )

    remaining = [
        cid
        for cid in ids
        if cid not in names
    ]

    print(
        "remaining:",
        len(remaining)
    )

    batch = remaining[
        :BATCH
    ]

    success = 0
    failed = 0

    for i, cid in enumerate(
        batch,
        start=1
    ):

        try:

            name = fetch_name(
                cid
            )

            if valid_name(name):

                names[cid] = name

                success += 1

                print(
                    f"{i}/{len(batch)} "
                    f"{cid} -> {name}"
                )

            else:

                failed += 1

                print(
                    f"{i}/{len(batch)} "
                    f"{cid} -> not found"
                )

        except Exception as e:

            failed += 1

            print(
                f"{i}/{len(batch)} "
                f"{cid} -> error: {e}"
            )

        if i % 20 == 0:

            save_map(
                names
            )

        time.sleep(
            WAIT
        )

    save_map(
        names
    )

    print("")
    print(
        "success:",
        success
    )
    print(
        "failed:",
        failed
    )
    print(
        "total Japanese:",
        len(names)
    )
    print(
        "remaining after:",
        len(ids) - len(names)
    )


if __name__ == "__main__":
    main()
