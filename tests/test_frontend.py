"""Tests for the custom card registration (requires Home Assistant)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

pytest.importorskip("homeassistant")
from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE

from custom_components.chunmi_ihcooker_slim import frontend
from custom_components.chunmi_ihcooker_slim.const import DATA_COORDINATOR, DATA_RECIPES, DOMAIN


class FakeResources:
    def __init__(self, items):
        self.items = items
        self.created = []
        self._async_ensure_loaded = AsyncMock()
        self.async_create_item = AsyncMock(side_effect=self.created.append)
        self.async_update_item = AsyncMock()

    def async_items(self):
        return self.items


def _hass(resources=None):
    data = {}
    if resources is not None:
        data[LOVELACE_DATA] = SimpleNamespace(
            resource_mode=MODE_STORAGE, resources=resources
        )
    return SimpleNamespace(
        data=data,
        http=SimpleNamespace(async_register_static_paths=AsyncMock()),
        async_create_task=Mock(side_effect=lambda coro: coro.close()),
    )


def test_register_card_adds_resource_once() -> None:
    resources = FakeResources([])
    hass = _hass(resources)

    asyncio.run(frontend.async_register_card(hass))

    hass.http.async_register_static_paths.assert_awaited_once()
    resources._async_ensure_loaded.assert_awaited_once()
    resources.async_create_item.assert_awaited_once_with(
        {"res_type": "module", "url": frontend.CARD_URL}
    )
    assert hass.data[frontend._REGISTERED]

    asyncio.run(frontend.async_register_card(hass))
    resources.async_create_item.assert_awaited_once()


def test_register_card_skips_existing_resource() -> None:
    resources = FakeResources([{"url": frontend.CARD_URL}])
    hass = _hass(resources)

    asyncio.run(frontend.async_register_card(hass))

    resources.async_create_item.assert_not_awaited()


def test_register_card_without_lovelace_does_not_mark_registered() -> None:
    hass = _hass()
    asyncio.run(frontend.async_register_card(hass))
    assert frontend._REGISTERED not in hass.data


def test_cookers_resolves_native_entities() -> None:
    coordinator = SimpleNamespace(
        identifier="aabbccddeeff",
        config_entry=SimpleNamespace(data={"name": "Kitchen cooker"}),
        info=SimpleNamespace(model="chunmi.ihcooker.slim"),
    )
    library = SimpleNamespace(language_mode="ha", language_label="English")
    runtime = {
        DOMAIN: {
            "entry-1": {
                DATA_COORDINATOR: coordinator,
                DATA_RECIPES: library,
            }
        }
    }
    hass = SimpleNamespace(data=runtime)

    class EntityRegistry:
        def async_get_entity_id(self, platform, domain, unique_id):
            if unique_id.endswith("_recipe_query"):
                return "text.cooker_recipe_query"
            if unique_id.endswith("_app_status") or unique_id.endswith("_status"):
                return "sensor.cooker_status"
            return None

    with (
        patch.object(
            frontend.dr,
            "async_get",
            return_value=SimpleNamespace(
                async_get_device=lambda identifiers: SimpleNamespace(
                    id="device-1", name="Kitchen cooker"
                )
            ),
        ),
        patch.object(frontend.er, "async_get", return_value=EntityRegistry()),
    ):
        cookers = frontend._cookers(hass)

    assert len(cookers) == 1
    cooker = cookers[0]
    assert cooker["device_id"] == "device-1"
    assert cooker["name"] == "Kitchen cooker"
    assert cooker["language_label"] == "English"
    assert cooker["entities"]["query"] == "text.cooker_recipe_query"
    assert cooker["entities"]["status"] == "sensor.cooker_status"
    assert len(cooker["entities"]) == len(frontend._ENTITY_LOOKUPS)
