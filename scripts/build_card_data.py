#!/usr/bin/env python3

import gzip
import json
import re
import urllib.request
from pathlib import Path

ASSETS = Path("src/main/assets")
ASSETS.mkdir(parents=True, exist_ok=True)

UA = "TCG-Deck-Studio-CardDataBuilder/4.0"

LOVECA_COMMIT = (
    "efe152f90bde74fbf002e62956e036dd102655a2"
)


# =========================================================
# 共通
# =========================================================

def download(url, timeout=120):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "application/json,text/plain,*/*",
        },
    )

    with urllib.request.urlopen(
        req,
        timeout=timeout
    ) as response:
        return response.read()


def get_json(url, gz=False):
    raw = download(url)

    if gz or url.endswith(".gz"):
        raw = gzip.decompress(raw)

    return json.loads(
        raw.decode("utf-8-sig")
    )


def safe(value):
    if value is None:
        return ""

    if isinstance(value, (list, tuple)):
        return " / ".join(
            str(x)
            for x in value
            if x is not None
        )

    if isinstance(value, dict):
        return ""

    return str(value)


def first_value(obj, keys):
    for key in keys:
        value = obj.get(key)

        if value is not None:
            text = safe(value).strip()

            if text:
                return text

    return ""


def write_js(game, cards):
    unique = {}

    for card in cards:
        cid = safe(
            card.get("id")
        ).strip()

        name = safe(
            card.get("name")
        ).strip()

        if not cid or not name:
            continue

        card["id"] = cid
        card["name"] = name

        unique[cid] = card

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
        for card in out
        if safe(
            card.get("image")
        ).strip()
    )

    print(
        f"{game}: "
        f"{len(out)} cards / "
        f"{image_count} images"
    )

    return {
        "cards": len(out),
        "images": image_count,
    }


# =========================================================
# ラブカ
# =========================================================

def loveca_image_url(card):
    image = first_value(
        card,
        (
            "img",
            "image",
            "image_url",
            "imageUrl",
        )
    )

    if not image:
        return ""

    if image.startswith(
        ("https://", "http://")
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

    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue

        cid = first_value(
            row,
            (
                "card_no",
                "cardNo",
                "id",
            )
        )

        if not cid:
            cid = f"LL-{i + 1}"

        name = first_value(
            row,
            (
                "name",
                "card_name",
                "cardName",
            )
        )

        if not name:
            name = (
                "エネルギー "
                + cid
            )

        cards.append({
            "id": cid,

            "name": name,

            "type": first_value(
                row,
                (
                    "type",
                    "card_type",
                )
            ),

            "series": first_value(
                row,
                (
                    "series",
                    "group",
                    "title",
                )
            ),

            "product": first_value(
                row,
                (
                    "product",
                    "pack",
                    "set",
                )
            ),

            "rarity": first_value(
                row,
                (
                    "rare",
                    "rarity",
                )
            ),

            "image":
                loveca_image_url(row),

            "color":
                safe(
                    row.get("color")
                ).strip(),
        })

    if len(cards) < 100:
        raise RuntimeError(
            f"LoveCa data too small: "
            f"{len(cards)}"
        )

    return cards


# =========================================================
# ポケカ
# =========================================================

def normalize_name(text):
    return re.sub(
        r"\s+",
        "",
        safe(text)
        .strip()
        .lower()
    )


def load_tcgdex_sets():
    """
    TCGdexの日本語セットを取得して
    カード名 + 販売タイトル -> 画像URL
    の対応表を作る。
    """

    sets_url = (
        "https://api.tcgdex.net/"
        "v2/ja/sets"
    )

    sets = get_json(sets_url)

    if not isinstance(sets, list):
        return {}

    image_map = {}

    for index, set_row in enumerate(sets):
        if not isinstance(
            set_row,
            dict
        ):
            continue

        set_id = safe(
            set_row.get("id")
        ).strip()

        if not set_id:
            continue

        try:
            detail = get_json(
                "https://api.tcgdex.net/"
                f"v2/ja/sets/{set_id}"
            )

        except Exception as error:
            print(
                "TCGdex set skip:",
                set_id,
                error
            )
            continue

        if not isinstance(
            detail,
            dict
        ):
            continue

        set_name = first_value(
            detail,
            (
                "name",
                "name_ja",
            )
        )

        cards = detail.get(
            "cards",
            []
        )

        if not isinstance(
            cards,
            list
        ):
            continue

        for card in cards:
            if not isinstance(
                card,
                dict
            ):
                continue

            card_name = safe(
                card.get("name")
            ).strip()

            image_base = safe(
                card.get("image")
            ).strip()

            if not (
                card_name
                and image_base
            ):
                continue

            image = (
                image_base.rstrip("/")
                + "/low.webp"
            )

            key_exact = (
                normalize_name(card_name),
                normalize_name(set_name),
            )

            image_map[
                key_exact
            ] = image

            # セット名一致しない時の予備
            key_name_only = (
                normalize_name(card_name),
                "",
            )

            image_map.setdefault(
                key_name_only,
                image
            )

        if (
            index > 0
            and index % 25 == 0
        ):
            print(
                "TCGdex sets loaded:",
                index
            )

    return image_map


def pokemon_type_label(raw):
    value = safe(raw).strip()

    mapping = {
        "Pokémon": "ポケモン",
        "Pokemon": "ポケモン",
        "Trainer": "トレーナーズ",
        "Energy": "エネルギー",
    }

    return mapping.get(
        value,
        value or "カード"
    )


def build_pokemon():
    """
    1ulce/pokemon-card-data:
      日本語名
      販売タイトル
      レギュレーション
      カード種類

    TCGdex:
      日本語カード画像

    を統合する。
    """

    base_url = (
        "https://raw.githubusercontent.com/"
        "1ulce/pokemon-card-data/"
        "main/index/all.json"
    )

    data = get_json(
        base_url
    )

    rows = (
        data.get(
            "faces",
            []
        )
        if isinstance(data, dict)
        else data
    )

    if not isinstance(
        rows,
        list
    ):
        raise RuntimeError(
            "Pokemon source invalid"
        )

    print(
        "Loading Pokemon image map..."
    )

    image_map = (
        load_tcgdex_sets()
    )

    print(
        "Pokemon image map:",
        len(image_map)
    )

    cards = []

    for i, row in enumerate(rows):
        if not isinstance(
            row,
            dict
        ):
            continue

        cid = first_value(
            row,
            (
                "slug",
                "id",
            )
        )

        if not cid:
            cid = f"PK-{i + 1}"

        name = first_value(
            row,
            (
                "name_ja",
                "name",
                "name_en",
            )
        )

        if not name:
            name = cid

        sale_title = first_value(
            row,
            (
                "first_set",
                "set_name_ja",
                "set",
            )
        )

        regulation = first_value(
            row,
            (
                "regulation_mark",
                "regulation",
            )
        )

        image = image_map.get(
            (
                normalize_name(name),
                normalize_name(
                    sale_title
                ),
            ),
            ""
        )

        if not image:
            image = image_map.get(
                (
                    normalize_name(name),
                    "",
                ),
                ""
            )

        cards.append({
            "id": cid,

            "name": name,

            "name_en": safe(
                row.get("name_en")
            ).strip(),

            "type":
                pokemon_type_label(
                    row.get("card_type")
                ),

            # index.html の販売タイトル用
            "saleTitle":
                sale_title,

            # 互換性用
            "series":
                sale_title,

            "product":
                sale_title,

            # index.html のReg用
            "regulation":
                regulation,

            "regulationMark":
                regulation,

            "rarity":
                first_value(
                    row,
                    (
                        "rarity",
                        "first_rarity",
                    )
                ),

            "image":
                image,
        })

    if len(cards) < 500:
        raise RuntimeError(
            f"Pokemon data too small: "
            f"{len(cards)}"
        )

    return cards


# =========================================================
# ユニアリ
# =========================================================

UNION_WORK_JA = {
    "BLEACH": "BLEACH 千年血戦篇",
    "BLUE LOCK": "ブルーロック",
    "MY HERO ACADEMIA": "僕のヒーローアカデミア",
    "JUJUTSU KAISEN": "呪術廻戦",
    "DEMON SLAYER": "鬼滅の刃",
    "CODE GEASS": "コードギアス 反逆のルルーシュ",
    "HUNTER X HUNTER": "HUNTER×HUNTER",
    "HUNTER×HUNTER": "HUNTER×HUNTER",
    "ONE PUNCH MAN": "ワンパンマン",
    "TEKKEN": "鉄拳7",
    "TEKKEN 7": "鉄拳7",
    "TALES OF ARISE": "Tales of ARISE",
    "DRAGON BALL": "ドラゴンボール",
    "DRAGON BALL SUPER": "ドラゴンボール超",
    "GINTAMA": "銀魂",
    "GODDESS OF VICTORY": "勝利の女神：NIKKE",
    "NIKKE": "勝利の女神：NIKKE",
    "SHANGRI-LA FRONTIER": "シャングリラ・フロンティア",
    "KAIJU NO. 8": "怪獣8号",
    "KAIJU NO 8": "怪獣8号",
    "THE IDOLM@STER": "アイドルマスター",
    "IDOLMASTER": "アイドルマスター",
    "BLACK CLOVER": "ブラッククローバー",
    "FULLMETAL ALCHEMIST": "鋼の錬金術師",
    "ATTACK ON TITAN": "進撃の巨人",
    "ONE PIECE": "ONE PIECE",
    "SWORD ART ONLINE": "ソードアート・オンライン",
    "SAO": "ソードアート・オンライン",
    "MADOKA": "魔法少女まどか☆マギカ",
    "MADOKA MAGICA": "魔法少女まどか☆マギカ",
    "CHAINSAW MAN": "チェンソーマン",
    "WIND BREAKER": "WIND BREAKER",
    "TO LOVE-RU": "To LOVEる-とらぶる-",
    "TO LOVE RU": "To LOVEる-とらぶる-",
    "KIMETSU": "鬼滅の刃",
}


def recursive_products(
    obj,
    set_name="",
    work_name="",
    out=None
):
    if out is None:
        out = []

    if isinstance(obj, list):
        for item in obj:
            recursive_products(
                item,
                set_name,
                work_name,
                out
            )

        return out

    if not isinstance(obj, dict):
        return out

    local_set = first_value(
        obj,
        (
            "setName",
            "set_name",
            "groupName",
            "group_name",
            "set",
        )
    ) or set_name

    local_work = first_value(
        obj,
        (
            "work",
            "workName",
            "title",
            "gameName",
            "game_name",
            "categoryName",
            "category_name",
        )
    ) or work_name

    for key in (
        "products",
        "items",
        "cards",
    ):
        value = obj.get(key)

        if isinstance(
            value,
            list
        ):
            for item in value:
                if not isinstance(
                    item,
                    dict
                ):
                    continue

                row = dict(item)

                row.setdefault(
                    "_set_name",
                    local_set
                )

                row.setdefault(
                    "_work_name",
                    local_work
                )

                out.append(row)

    for key, value in obj.items():
        if key in (
            "products",
            "items",
            "cards",
        ):
            continue

        if isinstance(
            value,
            (dict, list)
        ):
            recursive_products(
                value,
                local_set,
                local_work,
                out
            )

    return out


def union_japanese_name(row):
    """
    元データに日本語名があれば最優先。
    """

    return first_value(
        row,
        (
            "nameJa",
            "nameJA",
            "name_ja",
            "nameJp",
            "nameJP",
            "japaneseName",
            "japanese_name",
            "name",
            "cleanName",
            "productName",
            "product_name",
        )
    )


def union_japanese_image(row):
    """
    元データに日本版画像URLが存在すれば最優先。
    なければ英語版画像へフォールバック。
    """

    japanese = first_value(
        row,
        (
            "imageJa",
            "imageJA",
            "image_ja",
            "imageJp",
            "imageJP",
            "japaneseImage",
            "japanese_image",
            "imageUrlJa",
            "imageUrlJP",
            "image_url_ja",
            "image_url_jp",
        )
    )

    if japanese.startswith(
        ("https://", "http://")
    ):
        return japanese

    direct = first_value(
        row,
        (
            "imageUrl",
            "image_url",
            "imageURL",
            "image",
        )
    )

    if direct.startswith(
        ("https://", "http://")
    ):
        return direct

    product_id = first_value(
        row,
        (
            "productId",
            "product_id",
        )
    )

    if product_id.isdigit():
        return (
            "https://tcgplayer-cdn."
            "tcgplayer.com/product/"
            f"{product_id}_in_1000x1000.jpg"
        )

    return ""


def japanese_work_name(
    raw_work,
    set_name
):
    text = (
        raw_work
        or set_name
        or ""
    ).strip()

    upper = text.upper()

    for english, japanese in (
        UNION_WORK_JA.items()
    ):
        if english in upper:
            return japanese

    # 元から日本語ならそのまま
    if re.search(
        r"[\u3040-\u30ff\u3400-\u9fff]",
        text
    ):
        return text

    return text


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

    for i, row in enumerate(rows):
        sig = json.dumps(
            row,
            ensure_ascii=False,
            sort_keys=True,
            default=str
        )

        if sig in seen:
            continue

        seen.add(sig)

        name = union_japanese_name(
            row
        ).strip()

        if not name:
            continue

        product_id = first_value(
            row,
            (
                "productId",
                "product_id",
            )
        )

        cid = first_value(
            row,
            (
                "number",
                "cardNumber",
                "card_number",
                "collectorNumber",
                "collector_number",
                "id",
            )
        )

        if not cid:
            cid = (
                product_id
                or f"UA-{i + 1}"
            )

        set_name = first_value(
            row,
            (
                "_set_name",
                "setName",
                "set_name",
            )
        )

        raw_work = first_value(
            row,
            (
                "work",
                "workName",
                "work_name",
                "_work_name",
                "title",
                "gameName",
                "game_name",
            )
        )

        work = japanese_work_name(
            raw_work,
            set_name
        )

        cards.append({
            "id": cid,

            "name": name,

            # index.html の作品フィルター用
            "work": work,

            # 互換性用
            "series": work,

            "product":
                set_name,

            "type": first_value(
                row,
                (
                    "cardType",
                    "card_type",
                    "type",
                )
            ) or "カード",

            "rarity": first_value(
                row,
                (
                    "rarity",
                    "rare",
                )
            ),

            "image":
                union_japanese_image(
                    row
                ),

            "productId":
                product_id,
        })

    if len(cards) < 100:
        raise RuntimeError(
            f"Union Arena data too small: "
            f"{len(cards)}"
        )

    return cards


# =========================================================
# 実行
# =========================================================

def main():
    build_info = {}

    builders = {
        "loveca":
            build_loveca,

        "pokemon":
            build_pokemon,

        "union":
            build_union,
    }

    for game, builder in (
        builders.items()
    ):
        print(
            f"Building {game}..."
        )

        cards = builder()

        build_info[game] = (
            write_js(
                game,
                cards
            )
        )

    info_path = (
        ASSETS
        / "card_data_build_info.json"
    )

    info_path.write_text(
        json.dumps(
            {
                "version": 4,
                "data":
                    build_info,
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
            build_info,
            ensure_ascii=False,
            indent=2
        )
    )


if __name__ == "__main__":
    main()
