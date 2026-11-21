"""Consistency checks for the integration constants."""

from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "chunmi_ihcooker_slim"
    / "const.py"
)
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
