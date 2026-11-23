"""Consistency checks for the integration constants."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

COMPONENT = (
    Path(__file__).parents[1] / "custom_components" / "chunmi_ihcooker_slim"
)
MODULE_PATH = COMPONENT / "const.py"
spec = importlib.util.spec_from_file_location("chunmi_const", MODULE_PATH)
const = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(const)


def test_property_mappings_are_unique() -> None:
    entries = [(item["siid"], item["piid"]) for item in const.PROPERTIES.values()]
    assert len(entries) == len(set(entries))


def test_property_sets_are_consistent() -> None:
    assert const.SUPPORTED_PROPERTIES <= const.PROPERTIES.keys()
    assert const.WRITABLE_PROPERTIES <= const.SUPPORTED_PROPERTIES
    assert const.BOOLEAN_PROPERTIES <= const.WRITABLE_PROPERTIES


def test_action_mappings_are_unique() -> None:
    entries = list(const.ACTIONS.values())
    assert len(entries) == len(set(entries))
    assert const.VERIFIED_ACTIONS <= const.ACTIONS.keys()


def test_value_maps_cover_observed_states() -> None:
    assert 0 in const.STATUS_MAP and 5 in const.STATUS_MAP
    assert 11 in const.WORK_STATUS_MAP and 19 in const.WORK_STATUS_MAP
    assert const.FAULT_MAP[0] == "none"


def test_app_status_and_preset_constants() -> None:
    assert const.APP_STATUS_MAP[1] == "烹饪中"
    assert const.APP_STATUS_MAP[5] == "休眠中"
    assert const.SERVICE_START_PRESET == "start_preset"
    assert const.PRESET_METHOD_BUILT_IN == "built_in"


def test_action_argument_map_covers_every_action() -> None:
    assert set(const.ACTION_ARGUMENT_PIIDS) == set(const.ACTIONS)
    for action, piids in const.ACTION_ARGUMENT_PIIDS.items():
        assert len(piids) == len(set(piids)), action


def test_success_code_is_only_zero() -> None:
    assert const.SUCCESS_CODES == frozenset({0})


def test_recipe_constants() -> None:
    assert const.RECIPE_SOURCE_JSON == "json"
    assert const.RECIPE_LANGUAGE_HA == "ha"
    assert const.RECIPE_LANGUAGE_ORIGINAL == "original"
    assert "select" in const.PLATFORMS


def test_service_metadata_covers_every_registered_service() -> None:
    yaml = pytest.importorskip("yaml")
    services = yaml.safe_load((COMPONENT / "services.yaml").read_text(encoding="utf-8"))
    strings = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    expected = {
        "start_preset", "start_cook", "cancel_cooking", "pause",
        "start_cooking", "pause_cooking", "resume_cooking",
        "cancel_cooking_v2", "set_menu", "delete_menu", "continue_cooking",
        "next_step", "factory_reset", "set_charge", "get_selfcheck",
        "start_simple_recipe", "set_simple_menu", "search_recipes",
        "get_recipe", "start_recipe", "add_favorite", "remove_favorite",
        "list_favorites", "refresh_recipes", "set_recipe_language",
        "translate_recipe",
    }
    assert set(services) == expected
    assert set(strings["services"]) == expected


def test_english_translations_match_strings() -> None:
    strings = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
    english = json.loads(
        (COMPONENT / "translations" / "en.json").read_text(encoding="utf-8")
    )
    assert english["services"] == strings["services"]
