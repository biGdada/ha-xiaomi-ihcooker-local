"""Tests for the cook script helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "chunmi_ihcooker_slim"
    / "recipe.py"
)
spec = importlib.util.spec_from_file_location("chunmi_recipe", MODULE_PATH)
recipe = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(recipe)


def test_crc16_reference_vector() -> None:
    assert recipe.crc16(b"123456789") == 0x31C3


def test_gbk_roundtrip() -> None:
    encoded = recipe.encode_gbk("火锅")
    assert encoded == "bbf0b9f8"
    assert recipe.decode_gbk(encoded) == "火锅"
    assert recipe.decode_gbk("Manual") == "Manual"


def test_decode_menu() -> None:
    decoded = recipe.decode_menu("0900000001bbf0b9f800")
    assert decoded == {
        "raw": "0900000001bbf0b9f800",
        "index": 9,
        "menu_id": 1,
        "name": "火锅",
    }
    assert recipe.decode_menu(None) is None
    assert recipe.decode_menu("nonsense") == {"raw": "nonsense"}


def test_build_simple_profile() -> None:
    hex_data = recipe.build_simple_profile(
        minutes=7, fire=12, recipe_type=recipe.RECIPE_TYPE_SINGLE_FIRE
    )
    raw = bytes.fromhex(hex_data)
    assert len(raw) == recipe.DEFAULT_PROFILE_SIZE
    assert raw[0] == 3
    assert raw[1] == 2
    assert raw[2] == recipe.DEFAULT_MENU_INDEX
    assert raw[8] == 0 and raw[9] == 7
    assert raw[18] == recipe.RECIPE_TYPE_SINGLE_FIRE
    assert raw[33] == 12
    assert recipe.crc16(raw[:-2]) == int.from_bytes(raw[-2:], "big")


def test_profile_roundtrip() -> None:
    profile = recipe.CookProfile()
    profile.cook_time = 95
    profile.temperature = 185
    profile.menu_index = 2
    hex_data = profile.to_hex()
    restored = recipe.CookProfile.from_hex(hex_data)
    assert restored.cook_time == 95
    assert restored.temperature == 185
    assert restored.menu_index == 2
    assert restored.to_hex() == hex_data
    assert restored.summary()["cook_time_minutes"] == 95


def test_invalid_cook_data() -> None:
    with pytest.raises(ValueError):
        recipe.CookProfile("zzzz")
    with pytest.raises(ValueError):
        recipe.CookProfile(b"abc")
