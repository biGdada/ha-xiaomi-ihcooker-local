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
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    APP_STATUS_ERROR,
    APP_STATUS_MAP,
    DATA_ACTIVE_RECIPE_ID,
    DATA_COORDINATOR,
    DATA_RECIPES,
    DERIVED_APP_STATUS,
    DOMAIN,
    FAULT_MAP,
    FAULTY_WORK_STATUSES,
    MANUFACTURER,
    MODEL,
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
    SensorDef(
        DERIVED_APP_STATUS,
        "App status",
        icon="mdi:stove",
        source_key=PROP_STATUS,
        derived=DERIVED_APP_STATUS,
    ),
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
    async_add_entities(
        [
            CurrentActionSensor(coordinator),
            ActiveRecipeIdSensor(coordinator),
            RecipeLibrarySensor(coordinator, entry),
            RecipeTranslationSensor(coordinator, entry),
            RecipeRefreshSensor(coordinator, entry),
        ]
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
        if definition.derived == DERIVED_APP_STATUS:
            if (
                data.get(PROP_FAULT) not in (None, 0)
                or data.get(PROP_WORK_STATUS) in FAULTY_WORK_STATUSES
            ):
                return APP_STATUS_ERROR
            status = data.get(PROP_STATUS)
            return APP_STATUS_MAP.get(status, f"未知状态 {status}")
        value = data.get(self._source_key)
        if value is None:
            return None
        if definition.value_map is not None:
            return definition.value_map.get(value, f"unknown_{value}")
        return value


class CurrentActionSensor(IHCookerEntity, SensorEntity):
    """Human-readable action: recipe name, built-in mode, waiting, or Off."""

    def __init__(self, coordinator: IHCookerDataUpdateCoordinator) -> None:
        super().__init__(
            coordinator, "current_action", "Current action", source_key=PROP_STATUS
        )
        self._attr_icon = "mdi:pot-steam"

    @property
    def native_value(self) -> str:
        """Return the active recipe name or the current mode."""
        data = self.coordinator.data or {}
        status = data.get(PROP_STATUS)
        runtime = self.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]
        recipe_id = runtime.get(DATA_ACTIVE_RECIPE_ID)
        library = runtime.get(DATA_RECIPES)
        recipe = None
        if recipe_id and library is not None:
            recipe = getattr(library, "_by_id", {}).get(int(recipe_id))
        if status in (None, 0):
            if recipe_id:
                name = (
                    str(library.summary(recipe).get("name") or "Recipe")
                    if recipe and library is not None
                    else "Recipe"
                )
                return f"{name} — waiting for panel"
            return "Off"
        if recipe:
            return str(library.summary(recipe).get("name") or "External Recipe")
        menu_name = decode_menu(data.get(PROP_MENU)) or {}
        name = menu_name.get("name")
        if name and name not in ("Unknown", "—"):
            return str(name)
        return "External Recipe"


class ActiveRecipeIdSensor(IHCookerEntity, SensorEntity):
    """Active bundled recipe ID; blank for off/built-in modes."""

    def __init__(self, coordinator: IHCookerDataUpdateCoordinator) -> None:
        super().__init__(
            coordinator, "active_recipe_id", "Recipe ID", source_key=PROP_STATUS
        )
        self._attr_icon = "mdi:identifier"

    @property
    def native_value(self) -> str | int | None:
        """Return the active recipe ID when known."""
        data = self.coordinator.data or {}
        status = data.get(PROP_STATUS)
        runtime = self.hass.data[DOMAIN][self.coordinator.config_entry.entry_id]
        recipe_id = runtime.get(DATA_ACTIVE_RECIPE_ID)
        if status in (None, 0):
            return int(recipe_id) if recipe_id else ""
        if recipe_id:
            return int(recipe_id)
        return "unknown"


class _RecipeEntity(SensorEntity):
    """Base for recipe-library status sensors."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: IHCookerDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.identifier)},
            name=entry.data.get("name") or "Chunmi IH Cooker Slim",
            manufacturer=MANUFACTURER,
            model=getattr(coordinator.info, "model", MODEL) or MODEL,
        )

    @property
    def _library(self):
        return self.hass.data[DOMAIN][self._entry.entry_id][DATA_RECIPES]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._library.add_listener(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        self._library.remove_listener(self.async_write_ha_state)
        await super().async_will_remove_from_hass()


class RecipeLibrarySensor(_RecipeEntity):
    """Expose the recipe catalogue, favorites and last viewed recipe."""

    _attr_name = "Recipe library"
    _attr_icon = "mdi:book-open-variant"

    def __init__(
        self, coordinator: IHCookerDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_recipe_library"

    @property
    def native_value(self) -> int:
        return len(self._library.recipes)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        library = self._library
        return {
            "language": library.display_language,
            "language_label": library.language_label,
            "source": library.source,
            "last_refresh": library.last_refresh,
            "last_error": library.last_error,
            "favorite_count": len(library.favorites),
            "favorites": [
                library.summary(library._by_id[recipe_id])
                for recipe_id in sorted(library.favorites)
                if recipe_id in library._by_id
            ],
            "last_query": library.last_query,
            "last_search": library.last_search,
            "last_recipe": library.last_recipe,
            "translation_warning": library.translation_warning,
        }


class RecipeTranslationSensor(_RecipeEntity):
    """Show translation service problems from the last recipe refresh."""

    _attr_name = "Recipe translation status"
    _attr_icon = "mdi:translate"

    def __init__(
        self, coordinator: IHCookerDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_recipe_translation_status"

    @property
    def native_value(self) -> str:
        return self._library.translation_warning or "OK"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "failed_strings": self._library.translation_failures,
            "last_refresh": self._library.last_refresh,
        }


class RecipeRefreshSensor(_RecipeEntity):
    """Shared recipe-refresh state so every card sees the same progress."""

    _attr_name = "Recipe refresh status"
    _attr_icon = "mdi:sync"

    def __init__(
        self, coordinator: IHCookerDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_recipe_refresh_status"

    @property
    def native_value(self) -> str:
        return self._library.refresh_phase

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        library = self._library
        total = library.refresh_total
        done = library.refresh_done
        return {
            "in_progress": library.refresh_phase not in ("idle", "done"),
            "phase": library.refresh_phase,
            "done": done,
            "total": total,
            "percent": min(100, round(done / total * 100)) if total else 0,
        }
