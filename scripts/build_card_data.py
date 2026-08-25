#!/usr/bin/env python3
import gzip
import json
import sys
import urllib.request
from pathlib import Path

ASSETS = Path("src/main/assets")
ASSETS.mkdir(parents=True, exist_ok=True)

UA = "TCG-Deck-Studio-CardDataBuilder/1.0"

def download(url, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def get_json(url, gz=False):
    raw = download(url)
    if gz or url.endswith(".gz"):
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8-sig"))

def safe(v):
    if v is None:
        return ""
    if isinstance(v, (list, tuple)):
        return " / ".join(str(x) for x in v if x is not None)
    return str(v)

def write_js(game, cards):
    data = {}
    for c in cards:
        cid = safe(c.get("id")).strip()
        name = safe(c.get("name")).strip()
        if not cid or not name:
            continue
        c["id"] = cid
        c["name"] = name
        data[cid] = c

    out = list(data.values())
    payload = json.dumps(out, ensure_ascii=False, separators=(",", ":"))

    js = (
        "window.TCG_CARD_DATA=window.TCG_CARD_DATA||{};\n"
        f"window.TCG_CARD_DATA.{game}={payload};\n"
    )

    path = ASSETS / f"cards_{game}.js"
    path.write_text(js, encoding="utf-8")

    print(f"{game}: {len(out)} cards")
    return len(out)

def build_loveca():
    urls = [
        "https://raw.githubusercontent.com/wlt233/llocg_db/master/json/cards.json",
        "https://raw.githubusercontent.com/wlt233/llocg_db/main/json/cards.json",
    ]

    data = None
    last_error = None

    for url in urls:
        try:
            data = get_json(url)
            break
        except Exception as e:
            last_error = e

    if data is None:
        raise RuntimeError(f"LoveCa download failed: {last_error}")

    rows = list(data.values()) if isinstance(data, dict) else data
    cards = []

    for i, x in enumerate(rows or []):
        if not isinstance(x, dict):
            continue

        cid = safe(x.get("card_no") or x.get("id") or f"LL-{i+1}")
        name = safe(x.get("name")).strip()

        if not name:
            name = "エネルギー " + cid

        cards.append({
            "id": cid,
            "name": name,
            "type": safe(x.get("type")),
            "series": safe(x.get("series")),
            "product": safe(x.get("product")),
            "rarity": safe(x.get("rare") or x.get("rarity")),
            "image": "",
            "color": safe(x.get("color")),
        })

    return cards

def build_pokemon():
    data = get_json(
        "https://raw.githubusercontent.com/1ulce/pokemon-card-data/main/index/all.json"
    )

    rows = data.get("faces", []) if isinstance(data, dict) else data
    cards = []

    for i, x in enumerate(rows or []):
        if not isinstance(x, dict):
            continue

        slug = safe(x.get("slug") or f"pokemon-{i+1}")
        typ = safe(x.get("card_type"))

        typ = {
            "Pokémon": "ポケモン",
            "Pokemon": "ポケモン",
            "Trainer": "トレーナーズ",
            "Energy": "エネルギー"
        }.get(typ, typ)

        cards.append({
            "id": slug,
            "name": safe(x.get("name_ja") or x.get("name_en") or slug),
            "type": typ,
            "series": safe(x.get("first_set")),
            "product": safe(x.get("first_set")),
            "rarity": "",
            "regulation": safe(x.get("regulation_mark")),
            "image": "",
        })

    return cards

def recursive_products(obj, set_name="", out=None):
    if out is None:
        out = []

    if isinstance(obj, list):
        for x in obj:
            recursive_products(x, set_name, out)
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

    for key in ("products", "items", "cards"):
        val = obj.get(key)

        if isinstance(val, list):
            for x in val:
                if isinstance(x, dict):
                    y = dict(x)
                    y.setdefault("_set_name", local_set)
                    out.append(y)

    for k, v in obj.items():
        if k in ("products", "items", "cards"):
            continue

        if isinstance(v, (dict, list)):
            recursive_products(v, local_set, out)

    return out

def build_union():
    url = (
        "https://github.com/HanClinto/tcgjson/releases/"
        "latest/download/union-arena.json.gz"
    )

    data = get_json(url, gz=True)
    rows = recursive_products(data)

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

        cid = safe(
            x.get("number")
            or x.get("cardNumber")
            or x.get("card_number")
            or x.get("collectorNumber")
            or x.get("collector_number")
            or x.get("productId")
            or x.get("product_id")
            or x.get("id")
            or f"UA-{i+1}"
        ).strip()

        typ = safe(
            x.get("cardType")
            or x.get("card_type")
            or x.get("type")
        )

        rarity = safe(x.get("rarity"))

        set_name = safe(
            x.get("_set_name")
            or x.get("setName")
            or x.get("set_name")
        )

        image = safe(
            x.get("imageUrl")
            or x.get("image_url")
            or x.get("image")
            or x.get("imageURL")
        )

        cards.append({
            "id": cid,
            "name": name,
            "type": typ or "カード",
            "series": set_name,
            "product": set_name,
            "rarity": rarity,
            "image": image,
        })

    if len(cards) < 100:
        raise RuntimeError(
            f"Union Arena parser found only {len(cards)} cards"
        )

    return cards

def main():
    counts = {}

    builders = {
        "loveca": build_loveca,
        "pokemon": build_pokemon,
        "union": build_union,
    }

    for game, fn in builders.items():
        cards = fn()
        counts[game] = write_js(game, cards)

    info = ASSETS / "card_data_build_info.json"

    info.write_text(
        json.dumps(
            {"counts": counts},
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8",
    )

    print("Card data build complete:", counts)

if __name__ == "__main__":
    main()
