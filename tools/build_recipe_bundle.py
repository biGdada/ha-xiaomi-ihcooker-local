"""Build the bundled recipe catalogue for Chunmi IH Cooker Slim.

The catalogue is fetched from the public Joyami endpoints, converted to the
160-byte cook scripts used by ``chunmi.ihcooker.slim``, translated to English
once at build time, and written to ``recipes.json`` next to the component.

Usage::

    python tools/build_recipe_bundle.py
    python tools/build_recipe_bundle.py --input capture/slim_cloud_bundle.json
    python tools/build_recipe_bundle.py --input capture/slim_cloud_bundle.json --offline

The runtime integration never calls this script.  A refreshed catalogue can
also be downloaded at runtime with the ``refresh_recipes`` service, using the
bundled file as the fallback.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import requests

APP_ID = "202007190935014"
BASE = "https://gateway.joyami.com"
MODEL = "chunmi.ihcooker.slim"
SEARCH_PATH = "/microwaveoven/index/search"
DETAIL_PATH = "/microwaveoven/index/getRecipeDetailById"
TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "custom_components" / "chunmi_ihcooker_slim" / "recipes.json"
TRANSLATION_CACHE = ROOT / "capture" / "slim_translation_cache.json"

PROFILE_SIZE = 160
REQUEST_DELAY = 0.5


def signed_headers(method: str, path: str, vid: str = "1") -> dict[str, str]:
    """Return headers signed the same way the Mi Home plugin signs them."""
    timestamp = str(int(time.time() * 1000))
    minute = int(timestamp) // 60000
    nonce = base64.urlsafe_b64encode(
        os.urandom(8) + minute.to_bytes(4, "big")
    ).decode()
    payload = f"{APP_ID}&{timestamp}&{nonce}&{method}&{path}"
    signature = base64.urlsafe_b64encode(
        hashlib.sha256(payload.encode()).digest()
    ).decode()
    return {
        "appid": APP_ID,
        "version": f"{MODEL}: 9",
        "timestamp": timestamp,
        "nonce": nonce,
        "vid": vid,
        "signature": signature,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def api_get(path: str, params: dict[str, Any], attempts: int = 3) -> dict[str, Any]:
    """GET a Joyami endpoint, retrying transient gateway errors."""
    url = BASE + path + "?" + urlencode(params)
    last: Exception | None = None
    for _ in range(attempts):
        try:
            response = requests.get(
                url, headers=signed_headers("GET", path), timeout=60
            )
            if response.status_code == 200:
                return response.json()
            last = RuntimeError(f"HTTP {response.status_code}: {response.text[:120]}")
        except Exception as err:  # pragma: no cover - network dependent
            last = err
        time.sleep(1)
    raise RuntimeError(f"Joyami request failed for {path}: {last}")


def crc16_xmodem(data: bytes) -> int:
    """CRC-16/XMODEM used by CMCookProfile.toHexData()."""
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def encode_gbk(value: str) -> str:
    """Encode a name exactly like the plugin's ``getGBK()``."""
    return value.encode("gbk", errors="replace").hex() + "00"


def make_runnable(cookcode: str) -> str:
    """Normalize a slim cloud profile for local action 3/1."""
    try:
        data = bytearray(bytes.fromhex(cookcode))
    except ValueError as exc:
        raise ValueError("cookcode must be valid hex") from exc
    if len(data) != PROFILE_SIZE:
        raise ValueError(f"Unexpected cookcode length: {len(data)} bytes")
    if data[0] != 3 or data[2] != 9:
        raise ValueError("Not a Chunmi slim cloud cook script")
    data[19] = 1
    data[-2:] = crc16_xmodem(bytes(data[:-2])).to_bytes(2, "big")
    return data.hex()


def translation_cache() -> dict[str, str]:
    if TRANSLATION_CACHE.exists():
        try:
            return json.loads(TRANSLATION_CACHE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):  # pragma: no cover
            pass
    return {}


def save_cache(cache: dict[str, str]) -> None:
    TRANSLATION_CACHE.parent.mkdir(parents=True, exist_ok=True)
    TRANSLATION_CACHE.write_text(
        json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8"
    )


def has_chinese(value: object) -> bool:
    return isinstance(value, str) and any("\u4e00" <= c <= "\u9fff" for c in value)


def request_translation(texts: list[str]) -> dict[str, str]:
    """Translate a small batch, validating that the source echoed back."""
    url = TRANSLATE_URL + "?client=gtx&sl=zh-CN&tl=en&dt=t&q=" + quote(
        "\n".join(texts)
    )
    for attempt in range(5):
        try:
            response = requests.get(
                url, timeout=30, headers={"User-Agent": "Mozilla/5.0"}
            )
            if response.status_code == 429:
                time.sleep(min(2 ** (attempt + 1), 30))
                continue
            if response.status_code != 200:
                time.sleep(2 + attempt)
                continue
            segments = (response.json() or [[]])[0] or []
            if len(segments) != len(texts):
                return {}
            result: dict[str, str] = {}
            for source, segment in zip(texts, segments, strict=False):
                translated = str(segment[0] or "").rstrip("\n").strip()
                original = str(segment[1] or "").rstrip("\n").strip()
                if original != source.strip():
                    return {}
                result[source] = "" if translated == source else translated
            return result
        except Exception:  # pragma: no cover - network dependent
            time.sleep(2 + attempt)
    return {}


def translate_batch(texts: list[str], cache: dict[str, str]) -> None:
    """Translate a batch, splitting once if the endpoint rejects it."""
    result = request_translation(texts)
    if not result and len(texts) > 1:
        middle = len(texts) // 2
        result = request_translation(texts[:middle])
        result.update(request_translation(texts[middle:]))
    for text in texts:
        value = result.get(text, "")
        cache[text] = "" if has_chinese(value) else value


def translate_strings(strings: set[str], cache: dict[str, str], offline: bool) -> None:
    """Translate all missing strings politely, saving progress periodically."""
    pending = sorted(
        text
        for text in strings
        if text.strip()
        and has_chinese(text)
        and (not cache.get(text.strip()) or has_chinese(cache.get(text.strip())))
    )
    print(f"  {len(pending)} strings need translation", flush=True)
    if offline:
        for text in pending:
            cache[text.strip()] = ""
        return

    batch: list[str] = []
    size = 0
    done = 0

    def flush() -> None:
        nonlocal batch, size, done
        if not batch:
            return
        translate_batch(batch, cache)
        done += len(batch)
        batch, size = [], 0
        save_cache(cache)
        print(f"  translated {done}/{len(pending)}", flush=True)
        time.sleep(REQUEST_DELAY)

    for text in pending:
        key = text.strip()
        if "\n" in key:
            flush()
            translate_batch([key], cache)
            done += 1
            save_cache(cache)
            time.sleep(REQUEST_DELAY)
            continue
        if size + len(key) > 1200 or len(batch) >= 20:
            flush()
        batch.append(key)
        size += len(key) + 1
    flush()
    save_cache(cache)


def collect_strings(recipe: dict[str, Any]) -> set[str]:
    found: set[str] = set()

    def add(value: Any) -> None:
        if has_chinese(value):
            found.add(str(value).strip())

    for key in ("name", "description", "tips"):
        add(recipe.get(key))
    for ingredient in recipe.get("ingredients") or []:
        add(ingredient.get("name"))
        add(ingredient.get("quantity"))
    for step in recipe.get("steps") or []:
        add(step.get("content"))
    for food in recipe.get("foods") or []:
        add(food.get("foodName"))
        for ingredient in food.get("ingredients") or []:
            add(ingredient.get("name"))
            add(ingredient.get("quantity"))
    for tool in recipe.get("recipeTools") or []:
        add(tool.get("toolName"))
    return found


def normalize_detail(entry: dict[str, Any]) -> dict[str, Any] | None:
    """Accept either a saved capture entry or a live detail payload."""
    if "cookModel" in entry:
        result = entry.get("result") or {}
        item = entry.get("item") or {}
        model = entry.get("cookModel") or {}
        script = model.get("cookScript") or ""
        if model.get("model") != MODEL or len(script) != PROFILE_SIZE * 2:
            return None
    else:
        result = entry
        item = entry
        script = entry.get("cookcode") or ""
        if len(script) != PROFILE_SIZE * 2:
            return None
    try:
        runnable = make_runnable(script)
    except ValueError:
        return None
    name = str(result.get("name") or item.get("name") or "")
    return {
        "id": int(entry.get("id") or item.get("id")),
        "name": name,
        "description": result.get("description") or "",
        "tips": result.get("tips") or "",
        "duration": result.get("duration") or item.get("duration"),
        "defaultKeepWarmDuration": result.get("defaultKeepWarmDuration"),
        "minKeepWarmDuration": result.get("minKeepWarmDuration"),
        "maxKeepWarmDuration": result.get("maxKeepWarmDuration"),
        "coverImg": result.get("coverImg") or item.get("coverImg") or "",
        "isSingleCook": bool(result.get("isSingleCook")),
        "ingredients": result.get("ingredients") or [],
        "steps": result.get("steps") or [],
        "foods": result.get("foods") or [],
        "recipeTools": result.get("recipeTools") or [],
        "cookcode": script,
        "runnable_cookcode": runnable,
        "profile_type": bytes.fromhex(script)[18],
    }


def fetch_detail(item: dict[str, Any]) -> dict[str, Any] | None:
    try:
        result = api_get(
            DETAIL_PATH,
            {
                "recipeId": item["id"],
                "deviceId": "1",
                "model": MODEL,
                "menuType": "1",
                "language": "zh_CN",
            },
        ).get("result") or {}
    except Exception as err:  # pragma: no cover - network dependent
        print(f"  detail {item.get('id')} failed: {err}")
        return None
    detail = dict(result)
    detail["id"] = item["id"]
    detail["item"] = item
    detail["cookcode"] = next(
        (
            model.get("cookScript")
            for model in result.get("cookModels") or []
            if model.get("model") == MODEL
            and len(model.get("cookScript") or "") == PROFILE_SIZE * 2
        ),
        "",
    )
    return normalize_detail(detail)


def localize_recipe(recipe: dict[str, Any], cache: dict[str, str]) -> dict[str, Any]:
    def t(value: Any) -> str:
        key = str(value or "").strip()
        return cache.get(key, "") if has_chinese(value) else str(value or "")

    ingredients = [
        {
            "name_zh": item.get("name") or "",
            "name_en": t(item.get("name")),
            "quantity_zh": item.get("quantity") or "",
            "quantity_en": t(item.get("quantity")),
        }
        for item in recipe.get("ingredients") or []
    ]
    steps = [
        {
            "content_zh": item.get("content") or "",
            "content_en": t(item.get("content")),
            "image": item.get("coverImg") or "",
        }
        for item in recipe.get("steps") or []
    ]
    foods = [
        {
            "name_zh": food.get("foodName") or "",
            "name_en": t(food.get("foodName")),
            "ingredients": [
                {
                    "name_zh": item.get("name") or "",
                    "name_en": t(item.get("name")),
                    "quantity_zh": item.get("quantity") or "",
                    "quantity_en": t(item.get("quantity")),
                }
                for item in food.get("ingredients") or []
            ],
        }
        for food in recipe.get("foods") or []
    ]
    tools = [
        {
            "name_zh": tool.get("toolName") or "",
            "name_en": t(tool.get("toolName")),
            "image": tool.get("toolImg") or "",
        }
        for tool in recipe.get("recipeTools") or []
    ]
    return {
        "id": recipe["id"],
        "name_zh": recipe.get("name") or "",
        "name_en": t(recipe.get("name")),
        "name_gbk": encode_gbk(str(recipe.get("name") or "")),
        "description_zh": recipe.get("description") or "",
        "description_en": t(recipe.get("description")),
        "tips_zh": recipe.get("tips") or "",
        "tips_en": t(recipe.get("tips")),
        "duration": recipe.get("duration"),
        "default_keep_warm": recipe.get("defaultKeepWarmDuration"),
        "min_keep_warm": recipe.get("minKeepWarmDuration"),
        "max_keep_warm": recipe.get("maxKeepWarmDuration"),
        "cover_image": recipe.get("coverImg") or "",
        "is_single_cook": bool(recipe.get("isSingleCook")),
        "profile_type": recipe.get("profile_type"),
        "ingredients": ingredients,
        "steps": steps,
        "foods": foods,
        "tools": tools,
        "cookcode": recipe["cookcode"],
        "runnable_cookcode": recipe["runnable_cookcode"],
    }


def load_capture(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = list(payload.values()) if isinstance(payload, dict) else payload
    details: list[dict[str, Any]] = []
    for entry in entries:
        detail = normalize_detail(entry)
        if detail:
            details.append(detail)
    return details


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        help="Saved Joyami capture JSON instead of a live API fetch",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Do not call Google Translate; leave English fields empty",
    )
    args = parser.parse_args()

    if args.input:
        print(f"Loading catalogue from {args.input}…")
        details = load_capture(args.input)
    else:
        print("Fetching catalogue from Joyami…")
        search = api_get(
            SEARCH_PATH,
            {
                "keyword": "%",
                "pageNo": "1",
                "pageSize": "5000",
                "model": MODEL,
                "language": "zh_CN",
            },
        )
        items = search.get("result") or []
        print(f"  {len(items)} catalogue entries")
        details = []
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = [pool.submit(fetch_detail, item) for item in items]
            for index, future in enumerate(as_completed(futures), 1):
                detail = future.result()
                if detail:
                    details.append(detail)
                if index % 10 == 0:
                    print(f"  {index}/{len(items)}")
    details.sort(key=lambda item: int(item["id"]))
    print(f"  {len(details)} recipes with slim cookcodes")

    cache = translation_cache()
    strings: set[str] = set()
    for detail in details:
        strings |= collect_strings(detail)
    print(f"Translating {len(strings)} unique Chinese strings…")
    translate_strings(strings, cache, args.offline)

    bundle = [localize_recipe(detail, cache) for detail in details]
    OUTPUT.write_text(
        json.dumps(bundle, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    size = OUTPUT.stat().st_size / 1024
    print(f"Wrote {OUTPUT} ({size:.0f} KiB, {len(bundle)} recipes)")


if __name__ == "__main__":
    main()
