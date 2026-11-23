"""The Chunmi IH Cooker Slim local integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    EVENT_HOMEASSISTANT_STARTED,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)

from .const import (
    ATTR_DEVICE_ID,
    ATTR_FAVORITES_ONLY,
    ATTR_LANGUAGE,
    ATTR_LIMIT,
    ATTR_QUERY,
    ATTR_RECIPE,
    ACTIVE_WORK_STATUSES,
    CONF_HOST,
    CONF_INFORMATION,
    CONF_TIMEOUT,
    CONF_TOKEN,
    CONF_USER_ID,
    DATA_ACTIVE_RECIPE_ID,
    DATA_COORDINATOR,
    DATA_DEVICE,
    DATA_INFO,
    DATA_RECIPES,
    DATA_RECIPE_QUERY,
    DATA_SELECTED_PRESET,
    DOMAIN,
    PLATFORMS,
    PROP_STATUS,
    PROP_WORK_STATUS,
    PRESET_METHOD_BUILT_IN,
    PRESET_METHOD_RECIPE,
    SERVICES_REGISTERED,
    SERVICE_START_PRESET,
)
from .coordinator import IHCookerDataUpdateCoordinator
from .device import CookerError, IHCookerSlimDevice
from .frontend import async_register_card, async_register_card_config_ws
from .presets import PRESET_KEYS, get_preset
from .recipe import build_simple_profile
from .recipes import RecipeLibrary
from .service_schema import SERVICE_SCHEMAS

ATTR_MODE = "mode"
ATTR_MINUTES = "minutes"
ATTR_VALUE = "value"
ATTR_NAME = "name"
ATTR_COOK_DATA = "cook_data"
ATTR_BELL = "bell"
ATTR_MENU_ORDER = "menu_order"
ATTR_COMMAND = "command"
ATTR_PRESET = "preset"
ATTR_METHOD = "method"
ATTR_FIRE = "fire"
ATTR_TEMPERATURE = "temperature"

# HA normalizes `target` fields to lists before validating a service schema.
# The card sends a scalar device_id, so accept both scalar and list forms.
DEVICE_SCHEMA = {
    vol.Optional(ATTR_DEVICE_ID): vol.Any(cv.string, [cv.string]),
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
}

SERVICES = (
    SERVICE_START_PRESET,
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
    "search_recipes",
    "get_recipe",
    "start_recipe",
    "add_favorite",
    "remove_favorite",
    "list_favorites",
    "refresh_recipes",
    "set_recipe_language",
    "translate_recipe",
)

RECIPE_RESPONSE_SERVICES = frozenset(
    {
        "set_recipe_language",
        "search_recipes",
        "get_recipe",
        "start_recipe",
        "list_favorites",
        "refresh_recipes",
        "translate_recipe",
    }
)


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the domain and register the custom card."""
    hass.data.setdefault(DOMAIN, {})
    async_register_card_config_ws(hass)

    async def _async_startup(event: Any) -> None:
        await async_register_card(hass)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _async_startup)
    if hass.is_running:
        hass.async_create_task(async_register_card(hass))
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

    library = RecipeLibrary(hass, entry)
    await library.async_load()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        DATA_DEVICE: device,
        DATA_INFO: info,
        DATA_RECIPES: library,
        DATA_RECIPE_QUERY: "",
        DATA_ACTIVE_RECIPE_ID: None,
        DATA_SELECTED_PRESET: PRESET_KEYS[0],
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
        store = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        library = store.get(DATA_RECIPES) if isinstance(store, dict) else None
        if library is not None:
            await library.async_unload()
        stores = [
            value
            for value in hass.data.get(DOMAIN, {}).values()
            if isinstance(value, dict) and DATA_COORDINATOR in value
        ]
        if not stores:
            _async_remove_services(hass)
    return unload_ok


def _as_list(value: Any) -> list[Any]:
    """Normalize HA target fields, which may be scalar or lists."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _entry_id_for_call(hass: HomeAssistant, call: ServiceCall) -> str:
    """Resolve the targeted config entry, falling back to a single cooker."""
    runtime = hass.data.get(DOMAIN, {})
    for device_id in _as_list(call.data.get(ATTR_DEVICE_ID)):
        device_entry = dr.async_get(hass).async_get(str(device_id))
        if device_entry:
            for entry_id in device_entry.config_entries:
                if isinstance(runtime.get(entry_id), dict):
                    return entry_id
    for entity_id in _as_list(call.data.get(ATTR_ENTITY_ID)):
        entity = er.async_get(hass).async_get(str(entity_id))
        if entity and entity.config_entry_id and isinstance(
            runtime.get(entity.config_entry_id), dict
        ):
            return entity.config_entry_id
    candidates = [
        entry_id
        for entry_id, store in runtime.items()
        if isinstance(store, dict) and DATA_COORDINATOR in store
    ]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise HomeAssistantError("No Chunmi cooker is configured")
    raise HomeAssistantError("Multiple cookers configured; set device_id in the call")


def _get_coordinator(
    hass: HomeAssistant, call: ServiceCall
) -> IHCookerDataUpdateCoordinator:
    """Resolve the target cooker for a service call."""
    return hass.data[DOMAIN][_entry_id_for_call(hass, call)][DATA_COORDINATOR]


def _get_library(hass: HomeAssistant, call: ServiceCall) -> RecipeLibrary:
    """Resolve the recipe library for a service call."""
    return hass.data[DOMAIN][_entry_id_for_call(hass, call)][DATA_RECIPES]


def _clear_active_recipe(hass: HomeAssistant, call: ServiceCall) -> None:
    """Forget the previous cloud recipe when another action takes over."""
    entry_id = _entry_id_for_call(hass, call)
    runtime = hass.data[DOMAIN][entry_id]
    if runtime.get(DATA_ACTIVE_RECIPE_ID) is None:
        return
    runtime[DATA_ACTIVE_RECIPE_ID] = None
    runtime[DATA_RECIPES].async_update_entities()


def _recipe_arg(call: ServiceCall) -> Any:
    """Return the recipe ID supplied by the caller."""
    value = call.data.get(ATTR_RECIPE)
    if value is None:
        raise HomeAssistantError("Select a recipe ID first")
    return value


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

    async def start_preset(call: ServiceCall) -> None:
        """Start an app-like preset by name."""
        preset = get_preset(call.data[ATTR_PRESET])
        entry_id = _entry_id_for_call(hass, call)
        hass.data[DOMAIN][entry_id][DATA_SELECTED_PRESET] = preset.key
        method = call.data.get(ATTR_METHOD, PRESET_METHOD_BUILT_IN)
        _clear_active_recipe(hass, call)
        if method == PRESET_METHOD_RECIPE:
            profile = preset.build_profile(
                minutes=call.data.get(ATTR_MINUTES),
                fire=call.data.get(ATTR_FIRE),
                temperature=call.data.get(ATTR_TEMPERATURE),
            )
            await _async_device_method(hass, call, "start_recipe", preset.name, profile)
            return
        await _async_device_method(hass, call, "start_cook", preset.cook_mode)

    async def start_cook(call: ServiceCall) -> None:
        _clear_active_recipe(hass, call)
        await _async_device_method(hass, call, "start_cook", int(call.data[ATTR_MODE]))

    async def cancel_cooking(call: ServiceCall) -> None:
        await _get_coordinator(hass, call).async_call("cancel_cooking")
        _clear_active_recipe(hass, call)

    async def pause(call: ServiceCall) -> None:
        await _get_coordinator(hass, call).async_call("pause")

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
        await _async_device_method(hass, call, "pause_recover")

    async def cancel_cooking_v2(call: ServiceCall) -> None:
        await _async_device_method(hass, call, "cancel_cooking_v2")
        _clear_active_recipe(hass, call)

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
        await _async_device_method(hass, call, "next_step_cooking")

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
        await _async_device_method(
            hass, call, "start_recipe", call.data[ATTR_NAME], build_profile(call)
        )

    async def set_simple_menu(call: ServiceCall) -> None:
        await _async_device_method(
            hass,
            call,
            "set_menu",
            call.data[ATTR_NAME],
            build_profile(call),
            bool(call.data.get(ATTR_BELL, False)),
        )

    async def search_recipes(call: ServiceCall) -> dict[str, Any]:
        library = _get_library(hass, call)
        entry_id = _entry_id_for_call(hass, call)
        query = call.data.get(ATTR_QUERY) or hass.data[DOMAIN][entry_id].get(
            DATA_RECIPE_QUERY, ""
        )
        return {
            "recipes": library.search(
                query,
                limit=call.data.get(ATTR_LIMIT, 20),
                favorites_only=call.data.get(ATTR_FAVORITES_ONLY, False),
            ),
            "language": library.display_language,
            "total": len(library.recipes),
        }

    async def get_recipe(call: ServiceCall) -> dict[str, Any]:
        library = _get_library(hass, call)
        detail = library.detail(
            library.resolve(_recipe_arg(call)), language=call.data.get(ATTR_LANGUAGE)
        )
        library.async_update_entities()
        return detail

    async def start_recipe(call: ServiceCall) -> dict[str, Any]:
        entry_id = _entry_id_for_call(hass, call)
        runtime = hass.data[DOMAIN][entry_id]
        library = runtime[DATA_RECIPES]
        recipe = library.resolve(_recipe_arg(call))
        detail = library.detail(recipe)
        code = detail.get("runnable_cookcode")
        name_gbk = detail.get("name_gbk")
        if not code or not name_gbk:
            raise HomeAssistantError("Recipe has no runnable slim cookcode")
        await _async_device_method(hass, call, "start_cookcode", code, name_gbk)
        runtime[DATA_ACTIVE_RECIPE_ID] = int(recipe["id"])
        library.async_update_entities()
        data = _get_coordinator(hass, call).data or {}
        active_cooking = data.get(PROP_STATUS) in (1, 2, 3) or data.get(
            PROP_WORK_STATUS
        ) in ACTIVE_WORK_STATUSES
        return {
            "id": int(recipe["id"]),
            "name": library.summary(recipe)["name"],
            "active_cooking": active_cooking,
            "waiting_for_panel": not active_cooking,
        }

    async def add_favorite(call: ServiceCall) -> None:
        library = _get_library(hass, call)
        await library.async_set_favorite(
            int(library.resolve(_recipe_arg(call))["id"]), True
        )

    async def remove_favorite(call: ServiceCall) -> None:
        library = _get_library(hass, call)
        await library.async_set_favorite(
            int(library.resolve(_recipe_arg(call))["id"]), False
        )

    async def list_favorites(call: ServiceCall) -> dict[str, Any]:
        library = _get_library(hass, call)
        return {
            "recipes": [
                library.summary(library._by_id[recipe_id])
                for recipe_id in sorted(library.favorites)
                if recipe_id in library._by_id
            ]
        }

    async def refresh_recipes(call: ServiceCall) -> dict[str, Any]:
        library = _get_library(hass, call)
        count = await library.async_refresh()
        return {
            "count": count,
            "last_refresh": library.last_refresh,
            "error": library.last_error,
            "translation_warning": library.translation_warning,
        }

    async def set_recipe_language(call: ServiceCall) -> dict[str, Any]:
        library = _get_library(hass, call)
        library.language_mode = call.data[ATTR_LANGUAGE]
        library.async_update_entities()
        return {"language": library.display_language}

    async def translate_recipe(call: ServiceCall) -> dict[str, Any]:
        library = _get_library(hass, call)
        recipe = library.resolve(_recipe_arg(call))
        stats = await library.async_translate_recipe(recipe)
        return {
            "id": int(recipe["id"]),
            "name": library.summary(recipe)["name"],
            "translated": int(stats.get("translated", 0)),
            "failed": int(stats.get("failed", 0)),
            "error": stats.get("error"),
        }

    def register(
        name: str,
        handler: Any,
        schema: dict[Any, Any] | vol.Schema,
        supports_response: SupportsResponse = SupportsResponse.NONE,
    ) -> None:
        hass.services.async_register(
            DOMAIN,
            name,
            handler,
            schema=schema if isinstance(schema, vol.Schema) else vol.Schema(schema),
            supports_response=supports_response,
        )

    register(SERVICE_START_PRESET, start_preset, {
        **DEVICE_SCHEMA,
        vol.Required(ATTR_PRESET): vol.In(PRESET_KEYS),
        vol.Optional(ATTR_METHOD, default=PRESET_METHOD_BUILT_IN): vol.In(
            (PRESET_METHOD_BUILT_IN, PRESET_METHOD_RECIPE)
        ),
        vol.Optional(ATTR_MINUTES): vol.All(vol.Coerce(int), vol.Range(min=1, max=240)),
        vol.Optional(ATTR_FIRE): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
        vol.Optional(ATTR_TEMPERATURE): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=255)
        ),
    })
    register("start_cook", start_cook, {
        **DEVICE_SCHEMA,
        vol.Required(ATTR_MODE): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
    })
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
        vol.Required(ATTR_MENU_ORDER): vol.All(vol.Coerce(int), vol.Range(min=1, max=8)),
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

    recipe_handlers = {
        "search_recipes": search_recipes,
        "get_recipe": get_recipe,
        "start_recipe": start_recipe,
        "add_favorite": add_favorite,
        "remove_favorite": remove_favorite,
        "list_favorites": list_favorites,
        "refresh_recipes": refresh_recipes,
        "set_recipe_language": set_recipe_language,
        "translate_recipe": translate_recipe,
    }
    for name, handler in recipe_handlers.items():
        register(
            name,
            handler,
            SERVICE_SCHEMAS[name],
            SupportsResponse.OPTIONAL if name in RECIPE_RESPONSE_SERVICES
            else SupportsResponse.NONE,
        )


def _async_remove_services(hass: HomeAssistant) -> None:
    """Remove all services when the last config entry unloads."""
    for name in SERVICES:
        hass.services.async_remove(DOMAIN, name)
    hass.data[DOMAIN][SERVICES_REGISTERED] = False
