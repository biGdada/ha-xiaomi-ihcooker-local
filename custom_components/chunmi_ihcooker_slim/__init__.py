"""The Chunmi IH Cooker Slim local integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import (
    CONF_HOST,
    CONF_INFORMATION,
    CONF_TIMEOUT,
    CONF_TOKEN,
    CONF_USER_ID,
    DATA_COORDINATOR,
    DATA_DEVICE,
    DATA_INFO,
    DOMAIN,
    PLATFORMS,
    SERVICES_REGISTERED,
)
from .coordinator import IHCookerDataUpdateCoordinator
from .device import CookerError, IHCookerSlimDevice
from .recipe import build_simple_profile

ATTR_DEVICE_ID = "device_id"
ATTR_MODE = "mode"
ATTR_MINUTES = "minutes"
ATTR_VALUE = "value"
ATTR_NAME = "name"
ATTR_COOK_DATA = "cook_data"
ATTR_BELL = "bell"
ATTR_MENU_ORDER = "menu_order"
ATTR_COMMAND = "command"

DEVICE_SCHEMA = {vol.Optional(ATTR_DEVICE_ID): cv.string}


SERVICES = (
    "start_cook",
    "cancel_cooking",
    "pause",
    "start_cooking",
    "pause_cooking",
    "resume_cooking",
    "cancel_cooking_v2",
    "set_menu",
    "delete_menu",
    "continue_cooking",
    "next_step",
    "factory_reset",
    "set_charge",
    "get_selfcheck",
    "start_simple_recipe",
    "set_simple_menu",
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the domain."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a cooker from a config entry."""
    options = entry.options
    device = IHCookerSlimDevice(
        entry.data[CONF_HOST],
        entry.data[CONF_TOKEN],
        timeout=int(options.get(CONF_TIMEOUT, 5)),
        user_id=options.get(CONF_USER_ID, "uid_homeassistant"),
        information=options.get(CONF_INFORMATION, "info_030c01"),
    )
    info = await hass.async_add_executor_job(device.info)
    identifier = (
        getattr(info, "mac_address", None) or entry.unique_id or entry.data[CONF_HOST]
    ).replace(":", "").lower()

    coordinator = IHCookerDataUpdateCoordinator(
        hass, entry, device, identifier=identifier
    )
    coordinator.info = info
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        DATA_DEVICE: device,
        DATA_INFO: info,
    }

    _async_register_services(hass)
    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform(p) for p in PLATFORMS]
    )
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, [Platform(p) for p in PLATFORMS]
    )
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        stores = [
            value
            for value in hass.data.get(DOMAIN, {}).values()
            if isinstance(value, dict) and DATA_COORDINATOR in value
        ]
        if not stores:
            for service in SERVICES:
                hass.services.async_remove(DOMAIN, service)
            hass.data[DOMAIN][SERVICES_REGISTERED] = False
    return unload_ok


def _get_coordinator(hass: HomeAssistant, call: ServiceCall) -> IHCookerDataUpdateCoordinator:
    """Resolve the target cooker for a service call."""
    stores = hass.data.get(DOMAIN, {})
    device_id = call.data.get(ATTR_DEVICE_ID)
    if device_id:
        device_entry = dr.async_get(hass).async_get(device_id)
        if device_entry:
            for entry_id in device_entry.config_entries:
                store = stores.get(entry_id)
                if isinstance(store, dict) and DATA_COORDINATOR in store:
                    return store[DATA_COORDINATOR]
        raise HomeAssistantError(f"No cooker found for device_id {device_id}")

    candidates = [
        store[DATA_COORDINATOR]
        for store in stores.values()
        if isinstance(store, dict) and DATA_COORDINATOR in store
    ]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise HomeAssistantError("No Chunmi cooker is configured")
    raise HomeAssistantError("Multiple cookers configured; set device_id in the call")


async def _async_device_method(
    hass: HomeAssistant,
    call: ServiceCall,
    method: str,
    *args: Any,
) -> Any:
    coordinator = _get_coordinator(hass, call)
    try:
        result = await hass.async_add_executor_job(
            getattr(coordinator.device, method), *args
        )
    except CookerError as exc:
        raise HomeAssistantError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HomeAssistantError(f"{method} failed: {exc}") from exc
    await coordinator.async_request_refresh()
    return result


def _async_register_services(hass: HomeAssistant) -> None:
    """Register services once for all config entries."""
    if hass.data[DOMAIN].get(SERVICES_REGISTERED):
        return
    hass.data[DOMAIN][SERVICES_REGISTERED] = True

    async def start_cook(call: ServiceCall) -> None:
        await _async_device_method(hass, call, "start_cook", int(call.data[ATTR_MODE]))

    async def cancel_cooking(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call)
        await coordinator.async_call("cancel_cooking")

    async def pause(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass, call)
        await coordinator.async_call("pause")

    async def start_cooking(call: ServiceCall) -> None:
        await _async_device_method(
            hass,
            call,
            "start_recipe",
            call.data[ATTR_NAME],
            call.data[ATTR_COOK_DATA],
        )

    async def pause_cooking(call: ServiceCall) -> None:
        await _async_device_method(hass, call, "pause_cooking")

    async def resume_cooking(call: ServiceCall) -> None:
        await _async_device_method(hass, call, "resume_paused")

    async def cancel_cooking_v2(call: ServiceCall) -> None:
        await _async_device_method(hass, call, "cancel_cooking_v2")

    async def set_menu(call: ServiceCall) -> None:
        await _async_device_method(
            hass,
            call,
            "set_menu",
            call.data[ATTR_NAME],
            call.data[ATTR_COOK_DATA],
            bool(call.data.get(ATTR_BELL, False)),
        )

    async def delete_menu(call: ServiceCall) -> None:
        await _async_device_method(
            hass,
            call,
            "delete_menu",
            int(call.data[ATTR_MENU_ORDER]),
            bool(call.data.get(ATTR_BELL, False)),
        )

    async def continue_cooking(call: ServiceCall) -> None:
        await _async_device_method(hass, call, "continue_cooking")

    async def next_step(call: ServiceCall) -> None:
        await _async_device_method(hass, call, "next_step")

    async def factory_reset(call: ServiceCall) -> None:
        await _async_device_method(hass, call, "factory_reset")

    async def set_charge(call: ServiceCall) -> None:
        await _async_device_method(hass, call, "set_charge", call.data[ATTR_COOK_DATA])

    async def get_selfcheck(call: ServiceCall) -> None:
        await _async_device_method(
            hass, call, "get_selfcheck", int(call.data[ATTR_COMMAND])
        )

    def build_profile(call: ServiceCall) -> str:
        minutes = int(call.data[ATTR_MINUTES])
        kind = call.data[ATTR_MODE]
        value = int(call.data[ATTR_VALUE])
        if kind == "temperature":
            return build_simple_profile(
                minutes=minutes,
                recipe_type=3,
                temperature=value,
                menu_index=int(call.data.get("menu_index", 9)),
            )
        return build_simple_profile(
            minutes=minutes,
            recipe_type=1,
            fire=value,
            menu_index=int(call.data.get("menu_index", 9)),
        )

    async def start_simple_recipe(call: ServiceCall) -> None:
        profile = build_profile(call)
        await _async_device_method(
            hass, call, "start_recipe", call.data[ATTR_NAME], profile
        )

    async def set_simple_menu(call: ServiceCall) -> None:
        profile = build_profile(call)
        await _async_device_method(
            hass,
            call,
            "set_menu",
            call.data[ATTR_NAME],
            profile,
            bool(call.data.get(ATTR_BELL, False)),
        )

    def register(name: str, handler: Any, schema: dict[Any, Any]) -> None:
        hass.services.async_register(DOMAIN, name, handler, schema=vol.Schema(schema))

    register(
        "start_cook",
        start_cook,
        {
            **DEVICE_SCHEMA,
            vol.Required(ATTR_MODE): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=5)
            ),
        },
    )
    for name, handler in (
        ("cancel_cooking", cancel_cooking),
        ("pause", pause),
        ("pause_cooking", pause_cooking),
        ("resume_cooking", resume_cooking),
        ("cancel_cooking_v2", cancel_cooking_v2),
        ("continue_cooking", continue_cooking),
        ("next_step", next_step),
        ("factory_reset", factory_reset),
    ):
        register(name, handler, dict(DEVICE_SCHEMA))
    register("start_cooking", start_cooking, {
        **DEVICE_SCHEMA,
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_COOK_DATA): cv.string,
    })
    register("set_menu", set_menu, {
        **DEVICE_SCHEMA,
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_COOK_DATA): cv.string,
        vol.Optional(ATTR_BELL, default=False): cv.boolean,
    })
    register("delete_menu", delete_menu, {
        **DEVICE_SCHEMA,
        vol.Required(ATTR_MENU_ORDER): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        vol.Optional(ATTR_BELL, default=False): cv.boolean,
    })
    register("set_charge", set_charge, {
        **DEVICE_SCHEMA,
        vol.Required(ATTR_COOK_DATA): cv.string,
    })
    register("get_selfcheck", get_selfcheck, {
        **DEVICE_SCHEMA,
        vol.Required(ATTR_COMMAND): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
    })

    simple_schema = {
        **DEVICE_SCHEMA,
        vol.Required(ATTR_NAME): cv.string,
        vol.Required(ATTR_MINUTES): vol.All(vol.Coerce(int), vol.Range(min=1, max=240)),
        vol.Required(ATTR_MODE): vol.In(("fire", "temperature")),
        vol.Required(ATTR_VALUE): vol.All(vol.Coerce(int), vol.Range(min=1, max=1000)),
        vol.Optional("menu_index", default=9): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=255)
        ),
    }
    register("start_simple_recipe", start_simple_recipe, simple_schema)
    register("set_simple_menu", set_simple_menu, {
        **simple_schema,
        vol.Optional(ATTR_BELL, default=False): cv.boolean,
    })
