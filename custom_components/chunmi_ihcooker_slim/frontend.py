"""Serve the Chunmi IH Cooker Slim card and register it as a Lovelace resource.

The card is a real custom card, so it appears in Home Assistant's
``Add Card -> Search`` picker like any other HACS frontend card.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.lovelace.const import LOVELACE_DATA, MODE_STORAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DATA_COORDINATOR, DATA_RECIPES, DOMAIN

_LOGGER = logging.getLogger(__name__)

STATIC_PATH = f"/{DOMAIN}"
CARD_FILE = "chunmi-ihcooker-card.js"
_VERSION = json.loads((Path(__file__).parent / "manifest.json").read_text()).get(
    "version", "0"
)
CARD_URL = f"{STATIC_PATH}/{CARD_FILE}?v={_VERSION}"
_REGISTERED = f"{DOMAIN}_card_registered"
_STATIC = f"{DOMAIN}_card_static"

# Card key -> (platform, candidate unique-id suffixes).  Entities from the
# coordinator use the device MAC as unique-id prefix, while recipe entities use
# the config-entry ID; both are checked so old and new installs work.
_ENTITY_LOOKUPS: dict[str, tuple[str, tuple[str, ...]]] = {
    "cook_mode": ("select", ("start_preset",)),
    "profile": ("select", ("start_preset",)),
    "status": ("sensor", ("app_status", "status")),
    "current_action": ("sensor", ("current_action",)),
    "recipe_id": ("sensor", ("active_recipe_id",)),
    "current_mode": ("sensor", ("menu_name", "cook_mode")),
    "library": ("sensor", ("recipe_library",)),
    "translation": ("sensor", ("recipe_translation_status",)),
    "refreshing": ("sensor", ("recipe_refresh_status",)),
    "query": ("text", ("recipe_query",)),
}


async def async_register_card(hass: HomeAssistant) -> None:
    """Serve the card JS and add it to Lovelace resources once."""
    if hass.data.get(_REGISTERED):
        return

    www = Path(__file__).parent / "www"
    if not (www / CARD_FILE).is_file():
        _LOGGER.error("Chunmi IH Cooker Slim card JavaScript file is missing")
        return

    if not hass.data.get(_STATIC):
        try:
            await hass.http.async_register_static_paths(
                [StaticPathConfig(STATIC_PATH, str(www), cache_headers=False)]
            )
        except Exception:
            _LOGGER.exception("Failed to serve Chunmi IH Cooker Slim card JavaScript")
            return
        hass.data[_STATIC] = True

    if await _async_register_resource(hass):
        return

    # Lovelace can still be loading when HA_STARTED fires; retry briefly.
    hass.async_create_task(_async_retry_resource(hass))


async def _async_register_resource(hass: HomeAssistant) -> bool:
    """Add the JS to Lovelace storage resources. Return True when done."""
    lovelace_data = hass.data.get(LOVELACE_DATA)
    if lovelace_data is None:
        return False
    if lovelace_data.resource_mode != MODE_STORAGE:
        _LOGGER.warning(
            "Lovelace is in %s mode; add %s to your resources manually",
            lovelace_data.resource_mode,
            CARD_URL,
        )
        hass.data[_REGISTERED] = True
        return True
    try:
        resources = lovelace_data.resources
        await resources._async_ensure_loaded()  # noqa: SLF001 - storage collection API
        base = f"{STATIC_PATH}/{CARD_FILE}"
        for item in resources.async_items():
            url = str(item.get("url") or "")
            if url == CARD_URL or url == base or url.startswith(f"{base}?"):
                if url != CARD_URL:
                    await resources.async_update_item(
                        item["id"], {"res_type": "module", "url": CARD_URL}
                    )
                break
        else:
            await resources.async_create_item({"res_type": "module", "url": CARD_URL})
    except Exception:
        _LOGGER.exception("Failed to add Chunmi card to Lovelace resources")
        return False
    hass.data[_REGISTERED] = True
    _LOGGER.info("Chunmi IH Cooker Slim card registered at %s", CARD_URL)
    return True


async def _async_retry_resource(hass: HomeAssistant) -> None:
    """Keep trying while Lovelace finishes loading at startup."""
    for _ in range(5):
        await asyncio.sleep(2)
        if await _async_register_resource(hass):
            return
    _LOGGER.debug("Lovelace did not load; card resource not registered")


def _cookers(hass: HomeAssistant) -> list[dict[str, Any]]:
    """Describe configured cookers and their native entities for the card."""
    runtime = hass.data.get(DOMAIN, {})
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    result: list[dict[str, Any]] = []

    for entry_id, data in runtime.items():
        if not isinstance(data, dict) or DATA_COORDINATOR not in data:
            continue
        coordinator = data[DATA_COORDINATOR]
        identifier = coordinator.identifier
        device = device_registry.async_get_device(identifiers={(DOMAIN, identifier)})
        entities: dict[str, str | None] = {}
        for key, (platform, suffixes) in _ENTITY_LOOKUPS.items():
            found: str | None = None
            for suffix in suffixes:
                for prefix in (entry_id, identifier):
                    found = entity_registry.async_get_entity_id(
                        platform, DOMAIN, f"{prefix}_{suffix}"
                    )
                    if found:
                        break
                if found:
                    break
            entities[key] = found
        library = data.get(DATA_RECIPES)
        language = getattr(library, "language_mode", "ha")
        label = getattr(library, "language_label", "English")
        result.append(
            {
                "entry_id": entry_id,
                "device_id": device.id if device else None,
                "name": (device.name if device else None)
                or coordinator.config_entry.data.get("name")
                or "Chunmi IH Cooker Slim",
                "language": language,
                "language_label": label,
                "entities": entities,
            }
        )
    return result


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/card_config"})
@websocket_api.async_response
async def websocket_card_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the data the card needs to bind to this installation."""
    connection.send_result(msg["id"], {"cookers": _cookers(hass)})


def async_register_card_config_ws(hass: HomeAssistant) -> None:
    """Register the card configuration websocket command."""
    websocket_api.async_register_command(hass, websocket_card_config)
