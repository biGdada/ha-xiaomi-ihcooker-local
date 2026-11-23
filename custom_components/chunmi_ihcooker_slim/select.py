"""Select entity for the verified built-in cooking presets."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_COORDINATOR,
    DATA_SELECTED_PRESET,
    DOMAIN,
    MANUFACTURER,
    MODEL,
)
from .presets import PRESET_KEYS

DESCRIPTION = SelectEntityDescription(
    key="start_preset",
    name="Start preset",
    icon="mdi:stove",
    options=list(PRESET_KEYS),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the preset selector from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    async_add_entities([StartPresetSelect(coordinator)])


class StartPresetSelect(SelectEntity):
    """Preset used by the card's Start cooking button."""

    _attr_has_entity_name = True
    entity_description = DESCRIPTION

    def __init__(self, coordinator) -> None:
        self._coordinator = coordinator
        self._entry = coordinator.config_entry
        self._attr_unique_id = f"{coordinator.identifier}_start_preset"
        info = coordinator.info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.identifier)},
            name=self._entry.data.get("name") or "Chunmi IH Cooker Slim",
            manufacturer=MANUFACTURER,
            model=getattr(info, "model", MODEL) or MODEL,
        )

    @property
    def current_option(self) -> str | None:
        """Return the selected preset."""
        runtime = self.hass.data[DOMAIN][self._entry.entry_id]
        return str(runtime.get(DATA_SELECTED_PRESET) or PRESET_KEYS[0])

    async def async_select_option(self, option: str) -> None:
        """Remember the selected preset."""
        if option not in self.options:
            raise ValueError(f"Unknown preset: {option}")
        self.hass.data[DOMAIN][self._entry.entry_id][DATA_SELECTED_PRESET] = option
        self.async_write_ha_state()
