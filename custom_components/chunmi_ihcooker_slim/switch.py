"""Switch entities for the Chunmi IH Cooker Slim."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_COORDINATOR,
    DOMAIN,
    PROP_BUZZER_MARK,
    PROP_FINISH_PUSH,
    SUPPORTED_PROPERTIES,
)
from .coordinator import IHCookerDataUpdateCoordinator
from .entity import IHCookerEntity

SWITCHES = (
    (PROP_FINISH_PUSH, "Finish push", "mdi:bell-ring"),
    (PROP_BUZZER_MARK, "Buzzer", "mdi:bell"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switches from a config entry."""
    coordinator: IHCookerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    async_add_entities(
        IHCookerSwitch(coordinator, key, name, icon)
        for key, name, icon in SWITCHES
        if key in SUPPORTED_PROPERTIES
    )


class IHCookerSwitch(IHCookerEntity):
    """A writable boolean MIoT property."""

    def __init__(
        self,
        coordinator: IHCookerDataUpdateCoordinator,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator, key, name)
        self._attr_icon = icon

    @property
    def is_on(self) -> bool:
        """Return the current boolean value."""
        return bool((self.coordinator.data or {}).get(self._key))

    async def async_turn_on(self, **kwargs: object) -> None:
        """Turn the switch on."""
        await self.coordinator.async_set_property(self._key, True)

    async def async_turn_off(self, **kwargs: object) -> None:
        """Turn the switch off."""
        await self.coordinator.async_set_property(self._key, False)
