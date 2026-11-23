"""Service target normalization and English sensor labels (requires Home Assistant)."""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant")

import custom_components.chunmi_ihcooker_slim as component
from custom_components.chunmi_ihcooker_slim import sensor
from custom_components.chunmi_ihcooker_slim.const import (
    ATTR_DEVICE_ID,
    SERVICE_START_RECIPE,
)
from custom_components.chunmi_ihcooker_slim.service_schema import SERVICE_SCHEMAS


def test_device_schema_accepts_ha_normalized_targets() -> None:
    """HA turns `target` fields into lists before service schema validation."""
    schema = component.vol.Schema(component.DEVICE_SCHEMA)
    assert schema({ATTR_DEVICE_ID: "abc"})[ATTR_DEVICE_ID] == "abc"
    assert schema({ATTR_DEVICE_ID: ["abc"]})[ATTR_DEVICE_ID] == ["abc"]
    assert schema({"entity_id": ["sensor.foo"]})["entity_id"] == ["sensor.foo"]


def test_recipe_schema_accepts_list_device_id() -> None:
    result = SERVICE_SCHEMAS[SERVICE_START_RECIPE](
        {ATTR_DEVICE_ID: ["abc"], "recipe": 4209}
    )
    assert result[ATTR_DEVICE_ID] == ["abc"]


class _Library:
    def __init__(self) -> None:
        self._by_id = {
            4209: {"id": 4209, "name_zh": "大阪烧", "name_en": "Osaka pancake"}
        }
        self.recipes = list(self._by_id.values())

    def summary(self, recipe: dict, language: str | None = None) -> dict:
        key = "name_en" if language == "en" else "name_zh"
        return {"name": recipe.get(key)}


def test_english_name_prefers_bundled_english_recipe_name() -> None:
    library = _Library()
    assert sensor._english_name({}, library, 4209) == "Osaka pancake"
    assert sensor._english_name({}, library, None) is None


def test_english_name_maps_built_in_menu_to_english() -> None:
    # index 9, menu id 1 (hotpot), GBK name "火锅"
    data = {"menu": "0900000001bbf0b9f800"}
    assert sensor._english_name(data, _Library(), None) == "hotpot"


def test_english_name_translates_built_in_preset_name() -> None:
    name_hex = "火锅".encode("gbk").hex() + "00"
    data = {"menu": "0900001099" + name_hex}
    assert sensor._english_name(data, _Library(), None) == "Hotpot"


def test_english_name_translates_device_menu_name() -> None:
    name_hex = "大阪烧".encode("gbk").hex() + "00"
    data = {"menu": "0900001061" + name_hex}
    assert sensor._english_name(data, _Library(), None) == "Osaka pancake"


def test_english_name_ignores_untranslated_chinese_menu_name() -> None:
    name_hex = "未知菜谱".encode("gbk").hex() + "00"
    data = {"menu": "0900001062" + name_hex}
    assert sensor._english_name(data, _Library(), None) is None
