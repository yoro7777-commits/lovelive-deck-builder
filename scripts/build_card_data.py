#!/usr/bin/env python3

import gzip
import json
import urllib.request
from pathlib import Path

ASSETS = Path("src/main/assets")
ASSETS.mkdir(parents=True, exist_ok=True)

UA = "TCG-Deck-Studio-CardDataBuilder/3.0"


def download(url, timeout=120):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA}
    )
    with urllib.request.urlopen(
        req,
        timeout=timeout
    ) as r:
        return r.read()


def get_json(url, gz=False):
    raw = download(url)

    if gz or url.endswith(".gz"):
        raw = gzip.decompress(raw)

    return json.loads(
        raw.decode("utf-8-sig")
    )


def safe(v):
    if v is None:
        return ""

    if isinstance(v, (list, tuple)):
        return " / ".join(
            str(x)
            for x in v
            if x is not None
        )

    return str(v)


def write_js(game, cards):
    unique = {}

    for c in cards:
        cid = safe(
            c.get("id")
        ).strip()

        name = safe(
            c.get("name")
        ).strip()

        if not cid or not name:
            continue

        c["id"] = cid
        c["name"] = name

        unique[cid] = c

    out = list(
        unique.values()
    )

    if not out:
        raise RuntimeError(
            f"{game}: card count is 0"
        )

    payload = json.dumps(
        out,
        ensure_ascii=False,
        separators=(",", ":")
    )

    js = (
        "window.TCG_CARD_DATA="
        "window.TCG_CARD_DATA||{};\n"
        f"window.TCG_CARD_DATA.{game}="
        f"{payload};\n"
    )

    path = (
        ASSETS
        / f"cards_{game}.js"
    )

    path.write_text(
        js,
        encoding="utf-8"
    )

    image_count = sum(
        1
        for c in out
        if c.get("image")
    )

    print(
        f"{game}: "
        f"{len(out)} cards / "
        f"{image_count} images"
    )

    return {
        "cards": len(out),
        "images": image_count
    }


# =========================
# ラブカ
# =========================

LOVECA_COMMIT = (
    "efe152f90bde74fbf002e62956e036dd102655a2"
)


def loveca_image_url(x):
    image = safe(
        x.get("img")
        or x.get("image")
        or x.get("image_url")
        or x.get("imageUrl")
    ).strip()

    if not image:
        return ""

    if (
        image.startswith("https://")
        or image.startswith("http://")
    ):
        return image

    image = image.lstrip("./")

    return (
        "https://raw.githubusercontent.com/"
        "wlt233/llocg_db/"
        f"{LOVECA_COMMIT}/"
        f"{image}"
    )


def build_loveca():
    url = (
        "https://raw.githubusercontent.com/"
        "wlt233/llocg_db/"
        f"{LOVECA_COMMIT}/"
        "json/cards.json"
    )

    data = get_json(url)

    if isinstance(data, dict):
        rows = list(
            data.values()
        )
    elif isinstance(data, list):
        rows = data
    else:
        raise RuntimeError(
            "LoveCa JSON format invalid"
        )

    cards = []

    for i, x in enumerate(rows):
        if not isinstance(x, dict):
            continue

        cid = safe(
            x.get("card_no")
            or x.get("cardNo")
            or x.get("id")
            or f"LL-{i+1}"
        ).strip()

        name = safe(
            x.get("name")
            or x.get("card_name")
            or x.get("cardName")
        ).strip()

        if not name:
            name = (
                "エネルギー "
                + cid
            )

        cards.append({
            "id": cid,
            "name": name,

            "type": safe(
                x.get("type")
                or x.get("card_type")
            ),

            "series": safe(
                x.get("series")
                or x.get("group")
                or x.get("title")
            ),

            "product": safe(
                x.get("product")
                or x.get("pack")
                or x.get("set")
            ),

            "rarity": safe(
                x.get("rare")
                or x.get("rarity")
            ),

            "image":
                loveca_image_url(x),

            "color":
                safe(x.get("color")),
        })

    if len(cards) < 100:
        raise RuntimeError(
            f"LoveCa data too small: "
            f"{len(cards)}"
        )

    return cards


# =========================
# ポケカ
# =========================

def build_pokemon():
    """
    TCGdex 日本語カード一覧を利用。

    例:
    image =
    https://assets.tcgdex.net/ja/...
    
    ↓
    https://assets.tcgdex.net/ja/.../low.webp
    """

    url = (
        "https://api.tcgdex.net/"
        "v2/ja/cards"
    )

    rows = get_json(url)

    if not isinstance(rows, list):
        raise RuntimeError(
            "Pokemon TCGdex response invalid"
        )

    cards = []

    for i, x in enumerate(rows):
        if not isinstance(x, dict):
            continue

        cid = safe(
            x.get("id")
            or f"PK-{i+1}"
        ).strip()

        name = safe(
            x.get("name")
            or cid
        ).strip()

        image_base = safe(
            x.get("image")
        ).strip()

        image = ""

        if image_base:
            image = (
                image_base.rstrip("/")
                + "/low.webp"
            )

        cards.append({
            "id": cid,

            "name": name,

            "type":
                "ポケモンカード",

            "series": "",

            "product": "",

            "rarity": "",

            "regulation": "",

            "image": image,

            "localId": safe(
                x.get("localId")
            ),
        })

    if len(cards) < 500:
        raise RuntimeError(
            f"Pokemon data too small: "
            f"{len(cards)}"
        )

    return cards


# =========================
# ユニアリ
# =========================

def recursive_products(
    obj,
    set_name="",
    out=None
):
    if out is None:
        out = []

    if isinstance(obj, list):
        for x in obj:
            recursive_products(
                x,
                set_name,
                out
            )

        return out

    if not isinstance(obj, dict):
        return out

    local_set = safe(
        obj.get("setName")
        or obj.get("set_name")
        or obj.get("groupName")
        or obj.get("group_name")
        or obj.get("set")
        or set_name
    )

    for key in (
        "products",
        "items",
        "cards"
    ):
        val = obj.get(key)

        if isinstance(val, list):
            for x in val:
                if isinstance(x, dict):
                    y = dict(x)

                    y.setdefault(
                        "_set_name",
                        local_set
                    )

                    out.append(y)

    for k, v in obj.items():
        if k in (
            "products",
            "items",
            "cards"
        ):
            continue

        if isinstance(
            v,
            (dict, list)
        ):
            recursive_products(
                v,
                local_set,
                out
            )

    return out


def union_image_url(x):
    """
    まず元データに画像URLがあれば使う。
    なければ productId から
    TCGplayer CDN URLを生成。
    """

    direct = safe(
        x.get("imageUrl")
        or x.get("image_url")
        or x.get("image")
        or x.get("imageURL")
    ).strip()

    if direct.startswith(
        "https://"
    ):
        return direct

    product_id = safe(
        x.get("productId")
        or x.get("product_id")
    ).strip()

    if product_id.isdigit():
        return (
            "https://tcgplayer-cdn."
            "tcgplayer.com/product/"
            f"{product_id}_in_1000x1000.jpg"
        )

    return ""


def build_union():
    url = (
        "https://github.com/"
        "HanClinto/tcgjson/"
        "releases/latest/download/"
        "union-arena.json.gz"
    )

    data = get_json(
        url,
        gz=True
    )

    rows = recursive_products(
        data
    )

    cards = []
    seen = set()

    for i, x in enumerate(rows):
        sig = json.dumps(
            x,
            ensure_ascii=False,
            sort_keys=True,
            default=str
        )

        if sig in seen:
            continue

        seen.add(sig)

        name = safe(
            x.get("name")
            or x.get("cleanName")
            or x.get("productName")
            or x.get("product_name")
        ).strip()

        if not name:
            continue

        product_id = safe(
            x.get("productId")
            or x.get("product_id")
        ).strip()

        cid = safe(
            x.get("number")
            or x.get("cardNumber")
            or x.get("card_number")
            or x.get("collectorNumber")
            or x.get("collector_number")
            or product_id
            or x.get("id")
            or f"UA-{i+1}"
        ).strip()

        set_name = safe(
            x.get("_set_name")
            or x.get("setName")
            or x.get("set_name")
        )

        cards.append({
            "id": cid,

            "name": name,

            "type": safe(
                x.get("cardType")
                or x.get("card_type")
                or x.get("type")
            ) or "カード",

            "series": set_name,

            "product": set_name,

            "rarity": safe(
                x.get("rarity")
            ),

            "image":
                union_image_url(x),

            "productId":
                product_id,
        })

    if len(cards) < 100:
        raise RuntimeError(
            f"Union Arena data too small: "
            f"{len(cards)}"
        )

    return cards


# =========================
# 実行
# =========================

def main():
    info = {}

    builders = {
        "loveca": build_loveca,
        "pokemon": build_pokemon,
        "union": build_union,
    }

    for game, builder in builders.items():
        print(
            f"Building {game}..."
        )

        cards = builder()

        info[game] = write_js(
            game,
            cards
        )

    build_info = (
        ASSETS
        / "card_data_build_info.json"
    )

    build_info.write_text(
        json.dumps(
            {
                "version": 3,
                "data": info
            },
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    print(
        "Card data build complete"
    )

    print(
        json.dumps(
            info,
            ensure_ascii=False,
            indent=2
        )
    )


if __name__ == "__main__":
    main()
