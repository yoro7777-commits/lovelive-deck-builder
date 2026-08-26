#!/usr/bin/env python3

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR.parent / "src" / "main" / "assets"

OUTPUT_FILE = BASE_DIR / "union_ja_names.json"
SOURCE_FILE = ASSETS_DIR / "cards_union.js"

USER_AGENT = "TCG-Deck-Studio-Union-Japanese-Builder/1.0"

REQUEST_INTERVAL = 0.8
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3


def normalize_card_id(value):
    return str(value or "").strip()


def load_union_card_ids():
    if not SOURCE_FILE.exists():
        raise RuntimeError(
            f"Union card data not found: {SOURCE_FILE}"
        )

    text = SOURCE_FILE.read_text(
        encoding="utf-8"
    )

    marker = "window.TCG_CARD_DATA.union="

    pos = text.find(marker)

    if pos < 0:
        raise RuntimeError(
            "Could not find Union card data"
        )

    json_text = text[
        pos + len(marker):
    ].strip()

    if json_text.endswith(";"):
        json_text = json_text[:-1]

    cards = json.loads(
        json_text
    )

    if not isinstance(
        cards,
        list
    ):
        raise RuntimeError(
            "Union card data format invalid"
        )

    ids = []

    seen = set()

    for card in cards:

        if not isinstance(
            card,
            dict
        ):
            continue

        cid = normalize_card_id(
            card.get("id")
        )

        if not cid:
            continue

        if cid in seen:
            continue

        seen.add(cid)
        ids.append(cid)

    print(
        "Union card IDs:",
        len(ids)
    )

    return ids


def load_existing_map():
    if not OUTPUT_FILE.exists():
        return {}

    try:
        data = json.loads(
            OUTPUT_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(data, dict):
            return {
                str(k).strip():
                str(v).strip()
                for k, v in data.items()
                if str(k).strip()
                and str(v).strip()
            }

    except Exception as error:
        print(
            "Existing map load error:",
            error
        )

    return {}


def fetch_html(url):
    last_error = None

    for attempt in range(
        1,
        MAX_RETRIES + 1
    ):

        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent":
                        USER_AGENT,

                    "Accept":
                        "text/html,application/xhtml+xml",

                    "Accept-Language":
                        "ja,en;q=0.8",
                }
            )

            with urllib.request.urlopen(
                req,
                timeout=REQUEST_TIMEOUT
            ) as response:

                return response.read().decode(
                    "utf-8",
                    errors="replace"
                )

        except Exception as error:
            last_error = error

            print(
                f"Retry {attempt}/"
                f"{MAX_RETRIES}:",
                error
            )

            time.sleep(
                attempt * 2
            )

    raise last_error


def html_unescape_simple(text):
    replacements = {
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&#39;": "'",
        "&nbsp;": " ",
    }

    for key, value in (
        replacements.items()
    ):
        text = text.replace(
            key,
            value
        )

    text = re.sub(
        r"&#(\d+);",
        lambda m:
            chr(int(m.group(1))),
        text
    )

    return text


def strip_tags(text):
    text = re.sub(
        r"<br\s*/?>",
        " ",
        text,
        flags=re.I
    )

    text = re.sub(
        r"<[^>]+>",
        "",
        text
    )

    text = html_unescape_simple(
        text
    )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def extract_name_from_html(
    html,
    card_id
):
    patterns = [

        r'<h2[^>]*>(.*?)</h2>',

        r'<h1[^>]*class="[^"]*card[^"]*"[^>]*>'
        r'(.*?)</h1>',

        r'<div[^>]*class="[^"]*cardName[^"]*"[^>]*>'
        r'(.*?)</div>',

        r'<div[^>]*class="[^"]*card_name[^"]*"[^>]*>'
        r'(.*?)</div>',

    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html,
            flags=re.I | re.S
        )

        if not match:
            continue

        value = strip_tags(
            match.group(1)
        )

        if not value:
            continue

        if card_id in value:
            value = value.replace(
                card_id,
                ""
            ).strip()

        if value:
            return value

    title_match = re.search(
        r"<title[^>]*>(.*?)</title>",
        html,
        flags=re.I | re.S
    )

    if title_match:

        title = strip_tags(
            title_match.group(1)
        )

        title = title.replace(
            "カードリスト",
            ""
        )

        title = title.replace(
            "UNION ARENA",
            ""
        )

        title = title.replace(
            "ユニオンアリーナ",
            ""
        )

        title = title.replace(
            card_id,
            ""
        )

        title = re.sub(
            r"[｜|\-]+",
            " ",
            title
        )

        title = re.sub(
            r"\s+",
            " ",
            title
        ).strip()

        if title:
            return title

    return ""


def fetch_japanese_name(
    card_id
):
    encoded = urllib.parse.quote(
        card_id,
        safe=""
    )

    url = (
        "https://www.unionarena-tcg.com/"
        "jp/cardlist/detail.php"
        f"?card_no={encoded}"
    )

    html = fetch_html(
        url
    )

    name = extract_name_from_html(
        html,
        card_id
    )

    return name


def save_map(data):
    ordered = dict(
        sorted(
            data.items(),
            key=lambda x: x[0]
        )
    )

    OUTPUT_FILE.write_text(
        json.dumps(
            ordered,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )


def main():
    card_ids = load_union_card_ids()

    result = load_existing_map()

    print(
        "Existing Japanese names:",
        len(result)
    )

    success = 0
    skipped = 0
    failed = 0

    for index, card_id in enumerate(
        card_ids,
        start=1
    ):

        if card_id in result:
            skipped += 1
            continue

        try:
            name = fetch_japanese_name(
                card_id
            )

            if name:
                result[
                    card_id
                ] = name

                success += 1

                print(
                    f"[{index}/"
                    f"{len(card_ids)}] "
                    f"{card_id} -> "
                    f"{name}"
                )

            else:
                failed += 1

                print(
                    f"[{index}/"
                    f"{len(card_ids)}] "
                    f"{card_id} -> "
                    "name not found"
                )

        except Exception as error:
            failed += 1

            print(
                f"[{index}/"
                f"{len(card_ids)}] "
                f"{card_id} -> ERROR:",
                error
            )

        if (
            success > 0
            and
            success % 25 == 0
        ):
            save_map(
                result
            )

            print(
                "Intermediate save:",
                len(result)
            )

        time.sleep(
            REQUEST_INTERVAL
        )

    save_map(
        result
    )

    print(
        "Complete"
    )

    print(
        "Japanese names:",
        len(result)
    )

    print(
        "New:",
        success
    )

    print(
        "Skipped:",
        skipped
    )

    print(
        "Failed:",
        failed
    )


if __name__ == "__main__":
    main()
