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
    text = SRC.read_text(encoding="utf-8")
    marker = "window.TCG_CARD_DATA.union="
    p = text.find(marker)

    if p < 0:
        raise RuntimeError("Union data not found")

    raw = text[p + len(marker):].strip()

    if raw.endswith(";"):
        raw = raw[:-1]

    cards = json.loads(raw)

    ids = []
    seen = set()

    for c in cards:
        cid = str(c.get("id", "")).strip()

        if cid and cid not in seen:
            seen.add(cid)
            ids.append(cid)

    return ids


def load_map():
    if not OUT.exists():
        return {}

    try:
        data = json.loads(
            OUT.read_text(encoding="utf-8")
        )

        if isinstance(data, dict):
            return data

    except Exception:
        pass

    return {}


def save_map(data):
    OUT.write_text(
        json.dumps(
            dict(sorted(data.items())),
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print("saved:", len(data))


def clean_html(text):
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

    text = (
        text
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&nbsp;", " ")
    )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def fetch_name(card_id):
    encoded = urllib.parse.quote(
        card_id,
        safe=""
    )

    url = (
        "https://www.unionarena-tcg.com/"
        "jp/cardlist/detail.php"
        f"?card_no={encoded}"
    )

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent":
                "Mozilla/5.0",

            "Accept-Language":
                "ja,en;q=0.8"
        }
    )

    with urllib.request.urlopen(
        req,
        timeout=TIMEOUT
    ) as r:
        html = r.read().decode(
            "utf-8",
            errors="replace"
        )

    patterns = [
        r'<h2[^>]*>(.*?)</h2>',
        r'<div[^>]*class="[^"]*cardName[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*class="[^"]*card_name[^"]*"[^>]*>(.*?)</div>'
    ]

    for pattern in patterns:
        m = re.search(
            pattern,
            html,
            flags=re.I | re.S
        )

        if m:
            name = clean_html(
                m.group(1)
            )

            if card_id in name:
                name = name.replace(
                    card_id,
                    ""
                ).strip()

            if name:
                return name

    return ""


def main():
    ids = load_ids()
    names = load_map()

    remaining = [
        cid
        for cid in ids
        if cid not in names
    ]

    print("total:", len(ids))
    print("existing:", len(names))
    print("remaining:", len(remaining))

    batch = remaining[:BATCH]

    for i, cid in enumerate(
        batch,
        start=1
    ):
        try:
            name = fetch_name(cid)

            if name:
                names[cid] = name
                print(
                    f"{i}/{len(batch)} "
                    f"{cid} -> {name}"
                )
            else:
                print(
                    f"{i}/{len(batch)} "
                    f"{cid} -> not found"
                )

        except Exception as e:
            print(
                f"{i}/{len(batch)} "
                f"{cid} -> error: {e}"
            )

        if i % 20 == 0:
            save_map(names)

        time.sleep(WAIT)

    save_map(names)

    print(
        "remaining after:",
        len(ids) - len(names)
    )


if __name__ == "__main__":
    main()
