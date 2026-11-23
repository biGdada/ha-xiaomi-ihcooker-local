"""Tests for the app-like preset definitions."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

import pytest

COMPONENT = (
    Path(__file__).parents[1] / "custom_components" / "chunmi_ihcooker_slim"
)

# Load the component modules without importing the package __init__, which
# requires a full Home Assistant installation.
PACKAGE = "chunmi_test_pkg"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(COMPONENT)]
sys.modules[PACKAGE] = package


def load_module(name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(
        f"{PACKAGE}.{name}", COMPONENT / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[f"{PACKAGE}.{name}"] = module
    spec.loader.exec_module(module)
    return module


const = load_module("const")
recipe = load_module("recipe")
presets = load_module("presets")


def test_presets_cover_all_built_in_modes() -> None:
    assert {preset.cook_mode for preset in presets.PRESETS.values()} == set(
        const.COOK_MODE_MAP
    )
    assert presets.PRESET_KEYS == tuple(presets.PRESETS)


def test_preset_names_are_gbk_encodable() -> None:
    assert recipe.encode_gbk(presets.PRESETS["hotpot"].name) == "bbf0b9f800"
    for preset in presets.PRESETS.values():
        assert recipe.decode_gbk(recipe.encode_gbk(preset.name)) == preset.name


def test_preset_profile_uses_expected_fields() -> None:
    profile = presets.get_preset("hotpot")
    raw = bytes.fromhex(profile.build_profile(minutes=12, fire=33))
    assert len(raw) == recipe.DEFAULT_PROFILE_SIZE
    assert raw[8] == 0 and raw[9] == 12
    assert raw[18] == profile.profile_type
    assert raw[33] == 33
    assert recipe.crc16(raw[:-2]) == int.from_bytes(raw[-2:], "big")


def test_temperature_preset_uses_temperature_override() -> None:
    profile = presets.get_preset("stir_fry")
    raw = bytes.fromhex(profile.build_profile(temperature=175))
    assert raw[18] == recipe.RECIPE_TYPE_SINGLE_TEMPERATURE
    assert raw[32] == 175


def test_unknown_preset_raises() -> None:
    with pytest.raises(ValueError, match="Unknown cooking preset"):
        presets.get_preset("nope")
