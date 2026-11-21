"""Binary sensor entities for the Chunmi IH Cooker Slim."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ACTIVE_WORK_STATUSES,
    DATA_COORDINATOR,
    DOMAIN,
    FAULTY_WORK_STATUSES,
    PAUSED_WORK_STATUSES,
    PROP_FAULT,
    PROP_FINISH,
    PROP_STATUS,
    PROP_WORK_STATUS,
    SUPPORTED_PROPERTIES,
)
from .coordinator import IHCookerDataUpdateCoordinator
from .entity import IHCookerEntity


@dataclass(frozen=True)
class BinarySensorDef:
    key: str
    name: str
    source_key: str
    icon: str
    device_class: BinarySensorDeviceClass | None = None


BINARY_SENSORS = (
    BinarySensorDef(
        "cooking",
        "Cooking",
        PROP_WORK_STATUS,
        "mdi:stove",
        BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorDef("paused", "Paused", PROP_WORK_STATUS, "mdi:pause"),
    BinarySensorDef(
        "fault",
        "Fault",
        PROP_FAULT,
        "mdi:alert",
        BinarySensorDeviceClass.PROBLEM,
    ),
    BinarySensorDef("finished", "Finished", PROP_FINISH, "mdi:check-circle"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors from a config entry."""
    coordinator: IHCookerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    async_add_entities(
        IHCookerBinarySensor(coordinator, definition)
        for definition in BINARY_SENSORS
        if definition.source_key in SUPPORTED_PROPERTIES
    )


class IHCookerBinarySensor(IHCookerEntity, BinarySensorEntity):
    """A derived on/off state of the cooker."""

    def __init__(
        self,
        coordinator: IHCookerDataUpdateCoordinator,
        definition: BinarySensorDef,
    ) -> None:
        super().__init__(
            coordinator, definition.key, definition.name, source_key=definition.source_key
        )
        self._definition = definition
        self._attr_icon = definition.icon
        if definition.device_class:
            self._attr_device_class = definition.device_class

    @property
    def is_on(self) -> bool:
        """Return whether the derived condition is active."""
        data = self.coordinator.data or {}
        if self._key == "cooking":
            status = data.get(PROP_STATUS)
            work_status = data.get(PROP_WORK_STATUS)
            return status in (1, 2, 3) or work_status in ACTIVE_WORK_STATUSES
        if self._key == "paused":
            return data.get(PROP_WORK_STATUS) in PAUSED_WORK_STATUSES
        if self._key == "fault":
            return (
                data.get(PROP_FAULT) not in (None, 0)
                or data.get(PROP_WORK_STATUS) in FAULTY_WORK_STATUSES
            )
        return bool(data.get(PROP_FINISH))
