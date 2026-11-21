"""Shared entity base class for the Chunmi IH Cooker Slim."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import IHCookerDataUpdateCoordinator


class IHCookerEntity(CoordinatorEntity[IHCookerDataUpdateCoordinator]):
    """Base entity tied to a cooker config entry."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IHCookerDataUpdateCoordinator,
        key: str,
        name: str,
        *,
        source_key: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._key = key
        self._source_key = source_key or key
        self._attr_unique_id = f"{coordinator.identifier}_{key}"
        self._attr_name = name
        info = coordinator.info
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.identifier)},
            name=coordinator.config_entry.data.get("name") or "Chunmi IH Cooker Slim",
            manufacturer=MANUFACTURER,
            model=getattr(info, "model", MODEL) or MODEL,
            sw_version=getattr(info, "firmware_version", None),
            configuration_url=None,
        )

    @property
    def available(self) -> bool:
        """Require both a successful poll and a readable value."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.data.get(self._source_key) is not None
        )
