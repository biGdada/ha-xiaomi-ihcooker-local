"""Native text entity holding the recipe search query."""

from __future__ import annotations

from homeassistant.components.text import TextEntity, TextEntityDescription, TextMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_COORDINATOR,
    DATA_RECIPE_QUERY,
    DOMAIN,
    MANUFACTURER,
    MODEL,
)

DESCRIPTION = TextEntityDescription(
    key="recipe_query",
    name="Recipe search query",
    icon="mdi:magnify",
    mode=TextMode.TEXT,
    native_max=255,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the recipe query text entity from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([RecipeQueryText(coordinator)])


class RecipeQueryText(TextEntity):
    """Search term used by the ``search_recipes`` service."""

    _attr_has_entity_name = True
    entity_description = DESCRIPTION

    def __init__(self, coordinator) -> None:
        self._coordinator = coordinator
        self._entry = coordinator.config_entry
        self._attr_unique_id = f"{coordinator.identifier}_recipe_query"
        info = coordinator.info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.identifier)},
            name=entry_name(self._entry),
            manufacturer=MANUFACTURER,
            model=getattr(info, "model", MODEL) or MODEL,
        )

    @property
    def native_value(self) -> str:
        """Return the current query."""
        return str(
            self.hass.data[DOMAIN][self._entry.entry_id].get(DATA_RECIPE_QUERY) or ""
        )

    async def async_set_value(self, value: str) -> None:
        """Store a new query."""
        self.hass.data[DOMAIN][self._entry.entry_id][DATA_RECIPE_QUERY] = value.strip()
        self.async_write_ha_state()


def entry_name(entry: ConfigEntry) -> str:
    """Return the configured device name."""
    return str(entry.data.get("name") or "Chunmi IH Cooker Slim")
