#!/usr/bin/env python3

import re
import urllib.request


TEST_CARD = "UA02BT/JJK-1-001"

URL = (
    "https://www.unionarena-tcg.com/"
    "jp/cardlist/detail_iframe.php"
    "?card_no=UA02BT%2FJJK-1-001"
)


def clean(text):
    text = re.sub(
        r"<[^>]+>",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


def main():

    req = urllib.request.Request(
        URL,
        headers={
            "User-Agent":
                "Mozilla/5.0",

            "Accept-Language":
                "ja-JP,ja;q=0.9"
        }
    )

    with urllib.request.urlopen(
        req,
        timeout=20
    ) as response:

        html = response.read().decode(
            "utf-8",
            errors="replace"
        )

    print(
        "TEST CARD:",
        TEST_CARD
    )

    # カード画像のaltを探す
    pattern = (
        r'alt=["\']'
        + re.escape(TEST_CARD)
        + r'\s+([^"\']+)["\']'
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

        print(
            "CARD NAME:",
            name
        )

    else:

        print(
            "CARD NAME NOT FOUND"
        )


if __name__ == "__main__":
    main()
