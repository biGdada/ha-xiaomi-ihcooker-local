"""Tests for the slim recipe catalogue and translation helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import types

import pytest

COMPONENT = (
    Path(__file__).parents[1] / "custom_components" / "chunmi_ihcooker_slim"
)
PACKAGE = "chunmi_recipes_test_pkg"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(COMPONENT)]
sys.modules[PACKAGE] = package


def load_module(name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"{PACKAGE}.{name}", COMPONENT / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{PACKAGE}.{name}"] = module
    spec.loader.exec_module(module)
    return module


const = load_module("const")
recipe = load_module("recipe")
recipes = load_module("recipes")


def _library(language: str = "en") -> recipes.RecipeLibrary:
    library = object.__new__(recipes.RecipeLibrary)
    library.hass = SimpleNamespace(config=SimpleNamespace(language=language))
    library.language_mode = const.RECIPE_LANGUAGE_HA
    library._recipes = []
    library._by_id = {}
    library._favorites = set()
    library._listeners = set()
    library.last_query = ""
    library.last_search = []
    library.last_recipe = None
    return library


def _recipe() -> dict:
    cloud = bytearray(160)
    cloud[0] = 3
    cloud[1] = 0x10
    cloud[2] = 9
    cloud[7] = 0x80
    cloud[18] = 4
    cloud[19] = 2
    return {
        "id": 4432,
        "name_zh": "油焖大虾",
        "name_en": "Braised prawns",
        "description_zh": "经典家常菜",
        "description_en": "Classic home cooking",
        "tips_zh": "小火慢炖",
        "tips_en": "Simmer gently",
        "duration": 28,
        "cover_image": "",
        "ingredients": [
            {
                "name_zh": "大虾",
                "name_en": "prawns",
                "quantity_zh": "500克",
                "quantity_en": "500 g",
            }
        ],
        "steps": [{"content_zh": "热锅下油", "content_en": "Heat the pan", "image": ""}],
        "foods": [],
        "tools": [],
        "name_gbk": recipe.encode_gbk("油焖大虾"),
        "is_single_cook": False,
        "profile_type": 4,
        "cookcode": cloud.hex(),
        "runnable_cookcode": recipes.make_runnable(cloud.hex()),
    }


def test_language_helpers() -> None:
    assert recipes.language_code("en_US") == "en"
    assert recipes.language_code("de-DE") == "en"
    assert recipes.language_code("zh_Hans") == "zh"
    assert recipes.language_label("en") == "English"
    assert recipes.language_label("de_DE") == "Deutsch"
    assert recipes.language_label("zh_CN") == "简体中文"


def test_make_runnable_normalizes_slim_profile() -> None:
    cloud = bytearray(160)
    cloud[0] = 3
    cloud[1] = 0x10
    cloud[2] = 9
    cloud[7] = 0x80
    cloud[18] = 4
    cloud[19] = 2
    runnable = bytes.fromhex(recipes.make_runnable(cloud.hex()))

    assert len(runnable) == 160
    assert runnable[:3] == b"\x03\x10\x09"
    assert runnable[7] == 0x80
    assert runnable[19] == 1
    assert int.from_bytes(runnable[-2:], "big") == recipes.crc16_xmodem(runnable[:-2])


def test_merge_english_keeps_bundled_translations() -> None:
    bundled = _recipe()
    refreshed = [
        {
            "id": 4432,
            "name_zh": bundled["name_zh"],
            "name_en": "",
            "description_en": "",
            "tips_en": "",
            "ingredients": [{"name_en": "", "quantity_en": ""}],
            "steps": [{"content_en": ""}],
        }
    ]

    recipes.merge_english(refreshed, [bundled])

    assert refreshed[0]["name_en"] == "Braised prawns"
    assert refreshed[0]["ingredients"][0]["quantity_en"] == "500 g"
    assert refreshed[0]["steps"][0]["content_en"] == "Heat the pan"


def test_translate_missing_applies_cached_strings_without_network() -> None:
    item = _recipe()
    item["name_en"] = ""
    item["ingredients"][0]["quantity_en"] = ""
    cache = {"油焖大虾": "Braised prawns", "500克": "500 g"}

    stats = recipes.translate_missing([item], cache)

    assert stats["translated"] == 0
    assert item["name_en"] == "Braised prawns"
    assert item["ingredients"][0]["quantity_en"] == "500 g"


def test_translate_missing_surfaces_rate_limit(monkeypatch) -> None:
    item = _recipe()
    item["name_en"] = ""

    class Response:
        status_code = 429

    monkeypatch.setattr(recipes.requests, "get", lambda *args, **kwargs: Response())
    stats = recipes.translate_missing([item], {})

    assert stats["failed"] == 1
    assert "rate-limited" in stats["error"]
    assert item["name_en"] == ""


def test_poisoned_english_field_is_retranslated(monkeypatch) -> None:
    item = _recipe()
    item["name_en"] = item["name_zh"]
    cache = {item["name_zh"]: item["name_zh"]}

    class Response:
        status_code = 200

        def json(self):
            return [[["Braised prawns", item["name_zh"]]]]

    monkeypatch.setattr(recipes.requests, "get", lambda *args, **kwargs: Response())
    stats = recipes.translate_missing([item], cache)

    assert stats["translated"] == 1
    assert item["name_en"] == "Braised prawns"
    assert cache[item["name_zh"]] == "Braised prawns"


def test_prune_translations_drops_stale_keys() -> None:
    item = _recipe()
    translations = {"油焖大虾": "Braised prawns", "旧菜名": "Old recipe"}
    pruned = recipes._prune_translations([item], translations)
    assert pruned == {"油焖大虾": "Braised prawns"}


def test_resolve_rejects_ambiguous_names() -> None:
    library = _library()
    first = _recipe()
    second = _recipe()
    second["id"] = 4209
    library._recipes = [first, second]
    library._by_id = {first["id"]: first, second["id"]: second}

    assert library.resolve("4432") is first
    with pytest.raises(ValueError, match="Ambiguous recipe name"):
        library.resolve("油焖大虾")


def test_language_override_applies_to_summary_and_detail() -> None:
    library = _library()
    item = _recipe()
    library._recipes = [item]
    library._by_id = {item["id"]: item}

    assert library.summary(item, "original")["name"] == "油焖大虾"
    assert library.detail(item, "en")["name"] == "Braised prawns"
