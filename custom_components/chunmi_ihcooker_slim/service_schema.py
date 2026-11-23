"""Voluptuous schemas for chunmi_ihcooker_slim services."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_DEVICE_ID,
    ATTR_FAVORITES_ONLY,
    ATTR_LANGUAGE,
    ATTR_LIMIT,
    ATTR_QUERY,
    ATTR_RECIPE,
    RECIPE_LANGUAGE_HA,
    RECIPE_LANGUAGE_ORIGINAL,
    SERVICE_ADD_FAVORITE,
    SERVICE_GET_RECIPE,
    SERVICE_LIST_FAVORITES,
    SERVICE_REFRESH_RECIPES,
    SERVICE_REMOVE_FAVORITE,
    SERVICE_SEARCH_RECIPES,
    SERVICE_SET_RECIPE_LANGUAGE,
    SERVICE_START_RECIPE,
    SERVICE_TRANSLATE_RECIPE,
    PRESET_METHOD_BUILT_IN,
    PRESET_METHOD_RECIPE,
    SERVICE_START_PRESET,
)
from .presets import PRESET_KEYS

# HA's target selector may send either a scalar or a list of device IDs.
_TARGET = {
    vol.Optional(ATTR_DEVICE_ID): vol.Any(cv.string, [cv.string]),
    vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
}

_RECIPE_TARGET = {
    **_TARGET,
    vol.Optional(ATTR_RECIPE): vol.Any(cv.string, vol.Coerce(int)),
}

SERVICE_SCHEMAS: dict[str, vol.Schema] = {
    SERVICE_START_PRESET: vol.Schema(
        {
            **_TARGET,
            vol.Required("preset"): vol.In(PRESET_KEYS),
            vol.Optional("method", default=PRESET_METHOD_BUILT_IN): vol.In(
                (PRESET_METHOD_BUILT_IN, PRESET_METHOD_RECIPE)
            ),
            vol.Optional("minutes"): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=240)
            ),
            vol.Optional("fire"): vol.All(vol.Coerce(int), vol.Range(min=0, max=255)),
            vol.Optional("temperature"): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=255)
            ),
        }
    ),
    SERVICE_SEARCH_RECIPES: vol.Schema(
        {
            **_TARGET,
            vol.Optional(ATTR_QUERY, default=""): cv.string,
            vol.Optional(ATTR_LIMIT, default=20): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=100)
            ),
            vol.Optional(ATTR_FAVORITES_ONLY, default=False): cv.boolean,
        }
    ),
    SERVICE_GET_RECIPE: vol.Schema(
        {
            **_RECIPE_TARGET,
            vol.Optional(ATTR_LANGUAGE): vol.In(
                (RECIPE_LANGUAGE_HA, RECIPE_LANGUAGE_ORIGINAL)
            ),
        }
    ),
    SERVICE_START_RECIPE: vol.Schema(_RECIPE_TARGET),
    SERVICE_TRANSLATE_RECIPE: vol.Schema(_RECIPE_TARGET),
    SERVICE_ADD_FAVORITE: vol.Schema(_RECIPE_TARGET),
    SERVICE_REMOVE_FAVORITE: vol.Schema(_RECIPE_TARGET),
    SERVICE_LIST_FAVORITES: vol.Schema(_TARGET),
    SERVICE_REFRESH_RECIPES: vol.Schema(_TARGET),
    SERVICE_SET_RECIPE_LANGUAGE: vol.Schema(
        {
            **_TARGET,
            vol.Required(ATTR_LANGUAGE): vol.In(
                (RECIPE_LANGUAGE_HA, RECIPE_LANGUAGE_ORIGINAL)
            ),
        }
    ),
}
