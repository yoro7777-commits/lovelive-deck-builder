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

USER_AGENT = "TCG-Deck-Studio-Union-Japanese-Builder/2.0"

REQUEST_INTERVAL = 0.5
REQUEST_TIMEOUT = 20
MAX_RETRIES = 2

# 1回の実行で処理する最大件
