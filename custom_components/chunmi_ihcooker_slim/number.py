"""Number entity for the Chunmi IH Cooker Slim heat level."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_COORDINATOR,
    DOMAIN,
    PROP_HEAT_LEVEL,
    SUPPORTED_PROPERTIES,
    WRITABLE_PROPERTIES,
)
from .coordinator import IHCookerDataUpdateCoordinator
from .entity import IHCookerEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the heat level number from a config entry."""
    coordinator: IHCookerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    if (
        PROP_HEAT_LEVEL in SUPPORTED_PROPERTIES
        and PROP_HEAT_LEVEL in WRITABLE_PROPERTIES
    ):
        async_add_entities([IHCookerHeatLevel(coordinator)])


class IHCookerHeatLevel(IHCookerEntity, NumberEntity):
    """Writable heat level (2/7)."""

    def __init__(self, coordinator: IHCookerDataUpdateCoordinator) -> None:
        super().__init__(coordinator, PROP_HEAT_LEVEL, "Heat level")
        self._attr_icon = "mdi:fire"
        self._attr_mode = NumberMode.SLIDER
        self._attr_native_min_value = 0
        self._attr_native_max_value = 100
        self._attr_native_step = 1

    @property
    def native_value(self) -> float | None:
        """Return the current heat level."""
        value = (self.coordinator.data or {}).get(self._key)
        return float(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Write a new heat level."""
        await self.coordinator.async_set_property(self._key, int(value))
