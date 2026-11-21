"""Sensor entities for the Chunmi IH Cooker Slim."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DATA_COORDINATOR,
    DOMAIN,
    FAULT_MAP,
    PROP_APPOINT_TIME,
    PROP_CHARGE_PHASE,
    PROP_COOK_TIME,
    PROP_CUSTOM_DETAILS,
    PROP_ERROR_CODE,
    PROP_FAULT,
    PROP_FINISH,
    PROP_FIRE_GEARS,
    PROP_LEFT_TIME,
    PROP_MENU,
    PROP_PAUSE_TIME,
    PROP_PHASE,
    PROP_RECIPE_TYPE,
    PROP_STEP_FLAG,
    PROP_STEP_TIME,
    PROP_STEP_TOTAL_TIME,
    PROP_STATUS,
    PROP_TEMPERATURE,
    PROP_TARGET_TEMPERATURE,
    PROP_VERSION,
    PROP_WORK_STATUS,
    PROP_WORKING_TIME,
    PROP_MOVE_TEMPERATURE,
    RECIPE_TYPE_MAP,
    STATUS_MAP,
    SUPPORTED_PROPERTIES,
    WORK_STATUS_MAP,
)
from .coordinator import IHCookerDataUpdateCoordinator
from .entity import IHCookerEntity
from .recipe import decode_menu


@dataclass(frozen=True)
class SensorDef:
    key: str
    name: str
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    icon: str | None = None
    value_map: dict[int, str] | None = None
    entity_category: EntityCategory | None = None
    source_key: str | None = None
    derived: str | None = None


SENSORS: tuple[SensorDef, ...] = (
    SensorDef(PROP_STATUS, "Status", icon="mdi:state-machine", value_map=STATUS_MAP),
    SensorDef(PROP_WORK_STATUS, "Work status", icon="mdi:state-machine", value_map=WORK_STATUS_MAP),
    SensorDef(PROP_FAULT, "Fault", icon="mdi:alert-outline", value_map=FAULT_MAP),
    SensorDef(PROP_ERROR_CODE, "Error code", icon="mdi:alert-circle-outline"),
    SensorDef("menu_name", "Selected menu", icon="mdi:food", source_key=PROP_MENU, derived="menu_name"),
    SensorDef(PROP_MENU, "Menu data", icon="mdi:code", entity_category=EntityCategory.DIAGNOSTIC),
    SensorDef(PROP_PHASE, "Phase", icon="mdi:numeric"),
    SensorDef(PROP_RECIPE_TYPE, "Recipe type", icon="mdi:food-outline", value_map=RECIPE_TYPE_MAP),
    SensorDef(PROP_STEP_FLAG, "Step flag", icon="mdi:numeric", entity_category=EntityCategory.DIAGNOSTIC),
    SensorDef(PROP_CHARGE_PHASE, "Charge phase", icon="mdi:battery-charging", entity_category=EntityCategory.DIAGNOSTIC),
    SensorDef(PROP_FINISH, "Finished", icon="mdi:check-circle-outline", value_map={0: "no", 1: "yes"}),
    SensorDef(PROP_FIRE_GEARS, "Fire gears", icon="mdi:fire"),
    SensorDef(
        PROP_TEMPERATURE,
        "Temperature",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorDef(
        PROP_TARGET_TEMPERATURE,
        "Target temperature",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    SensorDef(
        PROP_MOVE_TEMPERATURE,
        "Move temperature",
        unit=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorDef(
        PROP_LEFT_TIME,
        "Time remaining",
        unit=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
    ),
    SensorDef(
        PROP_WORKING_TIME,
        "Working time",
        unit=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
    ),
    SensorDef(PROP_COOK_TIME, "Cook time", unit=UnitOfTime.MINUTES, icon="mdi:timer-outline"),
    SensorDef(PROP_APPOINT_TIME, "Appointment time", unit=UnitOfTime.MINUTES, icon="mdi:clock-outline"),
    SensorDef(PROP_PAUSE_TIME, "Pause time", unit=UnitOfTime.SECONDS, icon="mdi:pause"),
    SensorDef(PROP_STEP_TIME, "Step time", unit=UnitOfTime.SECONDS, icon="mdi:timer"),
    SensorDef(PROP_STEP_TOTAL_TIME, "Total step time", unit=UnitOfTime.SECONDS, icon="mdi:timer"),
    SensorDef(PROP_VERSION, "Firmware version", icon="mdi:information-outline", entity_category=EntityCategory.DIAGNOSTIC),
    SensorDef(PROP_CUSTOM_DETAILS, "Custom details", icon="mdi:code", entity_category=EntityCategory.DIAGNOSTIC),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from a config entry."""
    coordinator: IHCookerDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        DATA_COORDINATOR
    ]
    async_add_entities(
        IHCookerSensor(coordinator, definition)
        for definition in SENSORS
        if (definition.source_key or definition.key) in SUPPORTED_PROPERTIES
    )


class IHCookerSensor(IHCookerEntity, SensorEntity):
    """Representation of a cooker property as a sensor."""

    def __init__(
        self,
        coordinator: IHCookerDataUpdateCoordinator,
        definition: SensorDef,
    ) -> None:
        super().__init__(
            coordinator,
            definition.key,
            definition.name,
            source_key=definition.source_key,
        )
        self._definition = definition
        if definition.unit:
            self._attr_native_unit_of_measurement = definition.unit
        if definition.device_class:
            self._attr_device_class = SensorDeviceClass(definition.device_class)
        if definition.state_class:
            self._attr_state_class = SensorStateClass(definition.state_class)
        if definition.icon:
            self._attr_icon = definition.icon
        if definition.entity_category:
            self._attr_entity_category = definition.entity_category
        if definition.value_map:
            self._attr_options = list(definition.value_map.values())

    @property
    def native_value(self) -> Any:
        """Return the current value, mapping numeric enums to text."""
        data = self.coordinator.data or {}
        definition = self._definition
        if definition.derived == "menu_name":
            decoded = decode_menu(data.get(PROP_MENU))
            return decoded.get("name") if decoded else None
        value = data.get(self._source_key)
        if value is None:
            return None
        if definition.value_map is not None:
            return definition.value_map.get(value, f"unknown_{value}")
        return value
