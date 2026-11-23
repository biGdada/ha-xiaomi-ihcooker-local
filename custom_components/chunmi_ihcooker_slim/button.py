"""Button entities for the Chunmi IH Cooker Slim."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ACTION_CANCEL_COOKING,
    ACTION_PAUSE,
    DATA_COORDINATOR,
    DATA_RECIPES,
    DOMAIN,
    VERIFIED_ACTIONS,
)
from .coordinator import IHCookerDataUpdateCoordinator
from .entity import IHCookerEntity

BUTTONS = (
    (ACTION_CANCEL_COOKING, "Cancel cooking", "mdi:stop"),
    (ACTION_PAUSE, "Pause", "mdi:pause"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up action buttons from a config entry."""
    coordinator: IHCookerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    async_add_entities(
        IHCookerButton(coordinator, action, name, icon)
        for action, name, icon in BUTTONS
        if action in VERIFIED_ACTIONS
    )
    async_add_entities([RefreshRecipesButton(coordinator)])


class IHCookerButton(IHCookerEntity, ButtonEntity):
    """A button that calls a MIoT action."""

    def __init__(
        self,
        coordinator: IHCookerDataUpdateCoordinator,
        action: str,
        name: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator, action, name)
        self._action = action
        self._attr_icon = icon

    @property
    def available(self) -> bool:
        """Actions do not depend on a single property being readable."""
        return self.coordinator.last_update_success

    async def async_press(self) -> None:
        """Call the action."""
        await self.coordinator.async_call(self._action)


class RefreshRecipesButton(IHCookerEntity, ButtonEntity):
    """Refresh the Joyami recipe catalogue on demand."""

    def __init__(self, coordinator: IHCookerDataUpdateCoordinator) -> None:
        super().__init__(coordinator, "refresh_recipes", "Refresh recipes")
        self._attr_icon = "mdi:download"

    @property
    def available(self) -> bool:
        """The button does not depend on a readable cooker property."""
        return self.coordinator.last_update_success

    async def async_press(self) -> None:
        """Start a catalogue refresh."""
        library = self.hass.data[DOMAIN][self._coordinator.config_entry.entry_id][
            DATA_RECIPES
        ]
        await library.async_refresh()
