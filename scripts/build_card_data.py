#!/usr/bin/env python3

import gzip
import json
import re
import urllib.request
from pathlib import Path


# =========================================================
# 基本設定
# =========================================================

ASSETS = Path("src/main/assets")
ASSETS.mkdir(parents=True, exist_ok=True)

USER_AGENT = "TCG-Deck-Studio-Builder/6.0"

UNION_JA_MAP_FILE = Path(
    "scripts/union_ja_names.json"
)


# =========================================================
# 共通関数
# =========================================================

def download(url, timeout=120):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "ja,en;q=0.8",
        }
    )

    with urllib.request.urlopen(
        request,
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

    if isinstance(
        value,
        (list, tuple)
    ):

        return " / ".join(
            str(x)
            for x in value
            if x is not None
        )

    if isinstance(
        value,
        dict
    ):
        return ""

    return str(value)


def first_value(
    obj,
    keys
):

    for key in keys:

        value = obj.get(key)

        if value is None:
            continue

        text = safe(
            value
        ).strip()

        if text:
            return text

    return ""


def contains_japanese(
    text
):

    return bool(
        re.search(
            r"[\u3040-\u30ff\u3400-\u9fff]",
            safe(text)
        )
    )


def normalize(
    text
):

    return re.sub(
        r"\s+",
        "",
        safe(text)
        .strip()
        .lower()
    )


def write_js(
    game,
    cards
):

    unique = {}

    for card in cards:

        cid = safe(
            card.get("id")
        ).strip()

        name = safe(
            card.get("name")
        ).strip()

        if not cid:
            continue

        if not name:
            continue

        card["id"] = cid
        card["name"] = name

        unique[cid] = card


    output_cards = list(
        unique.values()
    )


    if not output_cards:

        raise RuntimeError(
            f"{game}: card count is 0"
        )


    payload = json.dumps(
        output_cards,
        ensure_ascii=False,
        separators=(",", ":")
    )


    output_path = (
        ASSETS
        /
        f"cards_{game}.js"
    )


    output_path.write_text(

        "window.TCG_CARD_DATA="
        "window.TCG_CARD_DATA||{};\n"

        f"window.TCG_CARD_DATA.{game}="
        f"{payload};\n",

        encoding="utf-8"

    )


    image_count = sum(
        1
        for card
        in output_cards
        if safe(
            card.get("image")
        ).strip()
    )


    japanese_count = sum(
        1
        for card
        in output_cards
        if contains_japanese(
            card.get("name", "")
        )
    )


    print(
        f"{game}: "
        f"{len(output_cards)} cards / "
        f"{image_count} images / "
        f"{japanese_count} Japanese names"
    )


    return {

        "cards":
            len(output_cards),

        "images":
            image_count,

        "japanese_names":
            japanese_count,

    }


# =========================================================
# ユニアリ 日本語名対応表
# =========================================================

def load_union_ja_map():

    if not UNION_JA_MAP_FILE.exists():

        print(
            "Union Japanese map: "
            "file not found"
        )

        return {}


    try:

        data = json.loads(
            UNION_JA_MAP_FILE
            .read_text(
                encoding="utf-8"
            )
        )


        if not isinstance(
            data,
            dict
        ):

            print(
                "Union Japanese map: "
                "invalid JSON format"
            )

            return {}


        result = {}


        for key, value in (
            data.items()
        ):

            card_id = str(
                key
            ).strip()

            japanese_name = str(
                value
            ).strip()


            if (
                card_id
                and
                japanese_name
            ):

                result[
                    card_id
                ] = japanese_name


        print(
            "Union Japanese name map:",
            len(result)
        )


        return result


    except Exception as error:

        print(
            "Union Japanese map error:",
            error
        )

        return {}


# =========================================================
# ラブカ
# =========================================================

LOVECA_COMMIT = (
    "efe152f90bde74fbf002e62956e036dd102655a2"
)


def loveca_image_url(
    row
):

    image = first_value(
        row,
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
        (
            "https://",
            "http://"
        )
    ):
        return image


    image = image.lstrip(
        "./"
    )


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


    data = get_json(
        url
    )


    if isinstance(
        data,
        dict
    ):

        rows = list(
            data.values()
        )

    elif isinstance(
        data,
        list
    ):

        rows = data

    else:

        raise RuntimeError(
            "LoveCa data invalid"
        )


    cards = []


    for index, row in enumerate(
        rows
    ):

        if not isinstance(
            row,
            dict
        ):
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

            cid = (
                f"LL-{index + 1}"
            )


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
                "カード "
                + cid
            )


        cards.append({

            "id":
                cid,

            "name":
                name,

            "type":
                first_value(
                    row,
                    (
                        "type",
                        "card_type",
                    )
                ),

            "series":
                first_value(
                    row,
                    (
                        "series",
                        "group",
                        "title",
                    )
                ),

            "product":
                first_value(
                    row,
                    (
                        "product",
                        "pack",
                        "set",
                    )
                ),

            "rarity":
                first_value(
                    row,
                    (
                        "rare",
                        "rarity",
                    )
                ),

            "image":
                loveca_image_url(
                    row
                ),

        })


    if len(cards) < 100:

        raise RuntimeError(
            "LoveCa data too small: "
            + str(len(cards))
        )


    return cards


# =========================================================
# ポケカ
# =========================================================

def load_tcgdex_sets():

    sets = get_json(
        "https://api.tcgdex.net/"
        "v2/ja/sets"
    )


    result = {}


    if not isinstance(
        sets,
        list
    ):

        return result


    for index, item in enumerate(
        sets
    ):

        if not isinstance(
            item,
            dict
        ):
            continue


        set_id = safe(
            item.get("id")
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
                "Pokemon set skip:",
                set_id,
                error
            )

            continue


        if not isinstance(
            detail,
            dict
        ):
            continue


        set_name = safe(
            detail.get("name")
        ).strip()


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


            if not card_name:
                continue


            image_url = ""


            if image_base:

                image_url = (
                    image_base
                    .rstrip("/")
                    +
                    "/low.webp"
                )


            result[
                (
                    normalize(
                        card_name
                    ),
                    normalize(
                        set_name
                    ),
                )
            ] = image_url


            result.setdefault(

                (
                    normalize(
                        card_name
                    ),
                    "",
                ),

                image_url

            )


        if (
            index > 0
            and
            index % 30 == 0
        ):

            print(
                "Pokemon sets:",
                index
            )


    return result


def pokemon_type(
    raw
):

    text = safe(
        raw
    ).strip()


    mapping = {

        "Pokémon":
            "ポケモン",

        "Pokemon":
            "ポケモン",

        "Trainer":
            "トレーナーズ",

        "Energy":
            "エネルギー",

    }


    return mapping.get(
        text,
        text or "カード"
    )


def build_pokemon():

    source = get_json(

        "https://raw.githubusercontent.com/"
        "1ulce/pokemon-card-data/"
        "main/index/all.json"

    )


    if isinstance(
        source,
        dict
    ):

        rows = source.get(
            "faces",
            []
        )

    else:

        rows = source


    if not isinstance(
        rows,
        list
    ):

        raise RuntimeError(
            "Pokemon data invalid"
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


    for index, row in enumerate(
        rows
    ):

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

            cid = (
                f"PK-{index + 1}"
            )


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
                normalize(
                    name
                ),
                normalize(
                    sale_title
                ),
            ),

            ""

        )


        if not image:

            image = image_map.get(

                (
                    normalize(
                        name
                    ),
                    "",
                ),

                ""

            )


        cards.append({

            "id":
                cid,

            "name":
                name,

            "name_en":
                safe(
                    row.get(
                        "name_en"
                    )
                ).strip(),

            "type":
                pokemon_type(
                    row.get(
                        "card_type"
                    )
                ),

            "saleTitle":
                sale_title,

            "series":
                sale_title,

            "product":
                sale_title,

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
            "Pokemon data too small: "
            + str(len(cards))
        )


    return cards


# =========================================================
# ユニアリ
# =========================================================

UNION_TITLE_JA = {

    "CODE GEASS":
        "コードギアス 反逆のルルーシュ",

    "JUJUTSU KAISEN":
        "呪術廻戦",

    "HUNTER X HUNTER":
        "HUNTER×HUNTER",

    "HUNTER×HUNTER":
        "HUNTER×HUNTER",

    "DEMON SLAYER":
        "鬼滅の刃",

    "TALES OF ARISE":
        "Tales of ARISE",

    "BLEACH":
        "BLEACH 千年血戦篇",

    "MY HERO ACADEMIA":
        "僕のヒーローアカデミア",

    "BLUE LOCK":
        "ブルーロック",

    "GINTAMA":
        "銀魂",

    "TEKKEN":
        "鉄拳7",

    "TEKKEN 7":
        "鉄拳7",

    "BLACK CLOVER":
        "ブラッククローバー",

    "SWORD ART ONLINE":
        "ソードアート・オンライン",

    "ONE PUNCH MAN":
        "ワンパンマン",

    "ATTACK ON TITAN":
        "進撃の巨人",

    "FULLMETAL ALCHEMIST":
        "鋼の錬金術師",

    "CHAINSAW MAN":
        "チェンソーマン",

    "KAIJU NO. 8":
        "怪獣8号",

    "KAIJU NO 8":
        "怪獣8号",

    "SHANGRI-LA FRONTIER":
        "シャングリラ・フロンティア",

    "NIKKE":
        "勝利の女神：NIKKE",

    "GODDESS OF VICTORY":
        "勝利の女神：NIKKE",

    "MADOKA MAGICA":
        "魔法少女まどか☆マギカ",

    "MADOKA":
        "魔法少女まどか☆マギカ",

    "TOKYO GHOUL":
        "東京喰種",

    "KINGDOM":
        "キングダム",

    "GURREN LAGANN":
        "天元突破グレンラガン",

}


UNION_CHARACTER_JA = {

    "ICHIGO KUROSAKI":
        "黒崎一護",

    "RUKIA KUCHIKI":
        "朽木ルキア",

    "SATORU GOJO":
        "五条悟",

    "YUJI ITADORI":
        "虎杖悠仁",

    "MEGUMI FUSHIGURO":
        "伏黒恵",

    "NOBARA KUGISAKI":
        "釘崎野薔薇",

    "TANJIRO KAMADO":
        "竈門炭治郎",

    "NEZUKO KAMADO":
        "竈門禰豆子",

    "ZENITSU AGATSUMA":
        "我妻善逸",

    "INOSUKE HASHIBIRA":
        "嘴平伊之助",

    "IZUKU MIDORIYA":
        "緑谷出久",

    "KATSUKI BAKUGO":
        "爆豪勝己",

    "SHOTO TODOROKI":
        "轟焦凍",

    "ALL MIGHT":
        "オールマイト",

    "GIYUU TOMIOKA":
        "冨岡義勇",

    "LELOUCH":
        "ルルーシュ",

    "C.C.":
        "C.C.",

    "SIMON":
        "シモン",

    "YOKO":
        "ヨーコ",

    "NIA":
        "ニア",

}


def recursive_union(
    obj,
    set_name="",
    work_name="",
    output=None
):

    if output is None:
        output = []


    if isinstance(
        obj,
        list
    ):

        for item in obj:

            recursive_union(
                item,
                set_name,
                work_name,
                output
            )

        return output


    if not isinstance(
        obj,
        dict
    ):

        return output


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

        value = obj.get(
            key
        )


        if not isinstance(
            value,
            list
        ):
            continue


        for item in value:

            if not isinstance(
                item,
                dict
            ):
                continue


            row = dict(
                item
            )


            row["_set_name"] = (
                local_set
            )

            row["_work_name"] = (
                local_work
            )


            output.append(
                row
            )


    for key, value in (
        obj.items()
    ):

        if key in (
            "products",
            "items",
            "cards",
        ):
            continue


        if isinstance(
            value,
            (
                list,
                dict
            )
        ):

            recursive_union(
                value,
                local_set,
                local_work,
                output
            )


    return output


def union_work_name(
    work,
    product
):

    text = (
        safe(
            work
        ).strip()
        or
        safe(
            product
        ).strip()
    )


    if contains_japanese(
        text
    ):
        return text


    upper = text.upper()


    for key, value in (
        UNION_TITLE_JA.items()
    ):

        if key in upper:
            return value


    return text


def union_card_name(
    row
):

    japanese = first_value(
        row,
        (
            "name_ja",
            "nameJa",
            "nameJA",
            "name_jp",
            "nameJp",
            "nameJP",
            "japaneseName",
            "japanese_name",
        )
    )


    if japanese:
        return japanese


    original = first_value(
        row,
        (
            "name",
            "cleanName",
            "productName",
            "product_name",
        )
    )


    if contains_japanese(
        original
    ):
        return original


    upper = (
        original
        .strip()
        .upper()
    )


    if upper in (
        UNION_CHARACTER_JA
    ):

        return (
            UNION_CHARACTER_JA[
                upper
            ]
        )


    return original


def union_image(
    row
):

    japanese_image = first_value(
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
        )
    )


    if japanese_image.startswith(
        (
            "https://",
            "http://"
        )
    ):

        return japanese_image


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
        (
            "https://",
            "http://"
        )
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
            f"{product_id}"
            "_in_1000x1000.jpg"

        )


    return ""


def union_type(
    raw
):

    text = (
        safe(raw)
        .strip()
        .lower()
    )


    mapping = {

        "character":
            "キャラクター",

        "field":
            "フィールド",

        "event":
            "イベント",

        "action point":
            "アクションポイント",

        "action point card":
            "アクションポイント",

        "ap":
            "アクションポイント",

    }


    return mapping.get(

        text,

        safe(raw).strip()
        or "カード"

    )


def build_union():

    data = get_json(

        "https://github.com/"
        "HanClinto/tcgjson/"
        "releases/latest/download/"
        "union-arena.json.gz",

        gz=True

    )


    rows = recursive_union(
        data
    )


    japanese_name_map = (
        load_union_ja_map()
    )


    cards = []

    seen = set()

    mapped_count = 0


    for index, row in enumerate(
        rows
    ):

        signature = json.dumps(
            row,
            ensure_ascii=False,
            sort_keys=True,
            default=str
        )


        if signature in seen:
            continue


        seen.add(
            signature
        )


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
                or
                f"UA-{index + 1}"
            )


        product = first_value(
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
                "_work_name",
                "work",
                "workName",
                "title",
                "gameName",
            )
        )


        work = union_work_name(
            raw_work,
            product
        )


        name = union_card_name(
            row
        )


        # =================================================
        # union_ja_names.json の日本語名を最優先
        # =================================================

        mapped_name = (
            japanese_name_map.get(
                cid,
                ""
            )
        )


        if mapped_name:

            name = mapped_name

            mapped_count += 1


        # カード番号の表記ゆれ対策
        if not mapped_name:

            normalized_id = (
                cid
                .replace(" ", "")
                .strip()
            )


            mapped_name = (
                japanese_name_map.get(
                    normalized_id,
                    ""
                )
            )


            if mapped_name:

                name = mapped_name

                mapped_count += 1


        if not name:
            continue


        cards.append({

            "id":
                cid,

            "name":
                name,

            "work":
                work,

            "series":
                work,

            "product":
                product,

            "type":
                union_type(
                    first_value(
                        row,
                        (
                            "cardType",
                            "card_type",
                            "type",
                        )
                    )
                ),

            "rarity":
                first_value(
                    row,
                    (
                        "rarity",
                        "rare",
                    )
                ),

            "image":
                union_image(
                    row
                ),

            "productId":
                product_id,

        })


    print(
        "Union mapped Japanese names:",
        mapped_count
    )


    if len(cards) < 100:

        raise RuntimeError(
            "Union Arena data too small: "
            + str(len(cards))
        )


    return cards


# =========================================================
# 実行
# =========================================================

def main():

    builders = {

        "loveca":
            build_loveca,

        "pokemon":
            build_pokemon,

        "union":
            build_union,

    }


    info = {}


    for game, builder in (
        builders.items()
    ):

        print(
            f"Building {game}..."
        )


        cards = (
            builder()
        )


        info[game] = write_js(
            game,
            cards
        )


    info_path = (
        ASSETS
        /
        "card_data_build_info.json"
    )


    info_path.write_text(

        json.dumps(
            {
                "version": 6,
                "data": info,
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
