"""Data update coordinator for the Chunmi IH Cooker Slim."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, DOMAIN
from .device import CookerActionError, CookerError, IHCookerSlimDevice

_LOGGER = logging.getLogger(__name__)


class IHCookerDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll the cooker over the local miIO protocol."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device: IHCookerSlimDevice,
        *,
        identifier: str,
    ) -> None:
        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            logger=_LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=int(scan_interval)),
        )
        self.config_entry = entry
        self.device = device
        self.identifier = identifier
        self.info: Any = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.hass.async_add_executor_job(self.device.read_properties)
        except Exception as exc:  # noqa: BLE001 - miio exception hierarchy varies
            raise UpdateFailed(f"Error communicating with cooker: {exc}") from exc

    async def async_call(self, action: str, params: list[Any] | None = None) -> Any:
        """Call an action off the event loop and force a state refresh."""
        try:
            result = await self.hass.async_add_executor_job(
                self.device.action, action, params
            )
        except CookerActionError as exc:
            raise HomeAssistantError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HomeAssistantError(f"Action {action} failed: {exc}") from exc
        await self.async_request_refresh()
        return result

    async def async_set_property(self, key: str, value: Any) -> None:
        """Write a property off the event loop and force a state refresh."""
        try:
            await self.hass.async_add_executor_job(self.device.set_property, key, value)
        except CookerError as exc:
            raise HomeAssistantError(str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HomeAssistantError(f"Setting {key} failed: {exc}") from exc
        await self.async_request_refresh()
