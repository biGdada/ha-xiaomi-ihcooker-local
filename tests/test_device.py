"""Tests for the MIoT action payloads sent by the device wrapper."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

import pytest

COMPONENT = (
    Path(__file__).parents[1] / "custom_components" / "chunmi_ihcooker_slim"
)

# Load the component modules without importing Home Assistant.
PACKAGE = "chunmi_device_test_pkg"
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
device_module = load_module("device")


class FakeMiotDevice:
    """Record ``call_action_by`` arguments without opening a socket."""

    def __init__(self, **kwargs: object) -> None:
        self.calls: list[tuple[int, int, list[object]]] = []

    def call_action_by(self, siid: int, aiid: int, params: list[object]) -> dict:
        self.calls.append((siid, aiid, params))
        return {"code": 0}


@pytest.fixture
def cooker(monkeypatch: pytest.MonkeyPatch) -> device_module.IHCookerSlimDevice:
    monkeypatch.setattr(device_module, "MiotDevice", FakeMiotDevice)
    return device_module.IHCookerSlimDevice(
        "192.0.2.1",
        "0123456789abcdef" * 2,
        user_id="uid_test",
        information="info_030c01",
    )


def test_start_cook_wraps_bare_value_in_piid_object(cooker) -> None:
    cooker.start_cook(3)
    assert cooker._device.calls == [(2, 1, [{"piid": 8, "value": 3}])]


def test_start_recipe_uses_spec_argument_order(cooker) -> None:
    name = "火锅"
    cook_data = "aabbcc"
    cooker.start_recipe(name, cook_data)
    assert cooker._device.calls == [
        (
            3,
            1,
            [
                {"piid": 22, "value": recipe.encode_gbk(name)},
                {"piid": 17, "value": cook_data},
                {"piid": 19, "value": "uid_test"},
            ],
        )
    ]


def test_set_menu_uses_spec_argument_order(cooker) -> None:
    name = "煲汤"
    cook_data = "01020304"
    cooker.set_menu(name, cook_data, bell=True)
    assert cooker._device.calls == [
        (
            3,
            5,
            [
                {"piid": 17, "value": cook_data},
                {"piid": 19, "value": "uid_test"},
                {"piid": 21, "value": 1},
                {"piid": 22, "value": recipe.encode_gbk(name)},
            ],
        )
    ]


def test_delete_menu_keeps_bell_before_menu_order(cooker) -> None:
    cooker.delete_menu(4, bell=True)
    assert cooker._device.calls == [
        (
            3,
            6,
            [
                {"piid": 19, "value": "uid_test"},
                {"piid": 20, "value": "info_030c01"},
                {"piid": 21, "value": 1},
                {"piid": 23, "value": 4},
            ],
        )
    ]


def test_empty_actions_still_send_empty_in_list(cooker) -> None:
    cooker.cancel_cooking()
    cooker.pause()
    assert cooker._device.calls == [(2, 2, []), (2, 3, [])]


def test_action_rejects_wrong_argument_count(cooker) -> None:
    with pytest.raises(device_module.CookerActionError, match="expects 1 argument"):
        cooker.action("start_cook", [])
    assert cooker._device.calls == []


def test_action_rejects_non_numeric_integer_argument(cooker) -> None:
    with pytest.raises(device_module.CookerActionError, match="must be a number"):
        cooker.action("start_cook", ["hotpot"])


def test_action_rejects_code_one(cooker, monkeypatch) -> None:
    """Firmware 2.2.0_0005 uses code 1 for a refused action, not success."""
    monkeypatch.setattr(cooker._device, "call_action_by", lambda *_args: {"code": 1})
    with pytest.raises(device_module.CookerActionError, match="MIoT error 1"):
        cooker.start_cook(3)


def test_action_surfaces_miot_error_code(cooker, monkeypatch) -> None:
    monkeypatch.setattr(
        cooker._device,
        "call_action_by",
        lambda *_args: {"code": -4003},
    )
    with pytest.raises(device_module.CookerActionError, match="does not exist"):
        cooker.cancel_cooking()


def test_argument_map_covers_every_action() -> None:
    assert set(const.ACTION_ARGUMENT_PIIDS) == set(const.ACTIONS)
    for action, piids in const.ACTION_ARGUMENT_PIIDS.items():
        assert len(piids) == len(set(piids)), action
        assert all(isinstance(piid, int) and piid > 0 for piid in piids), action
    for piid in const.ACTION_INTEGER_ARGUMENTS:
        assert any(piid in piids for piids in const.ACTION_ARGUMENT_PIIDS.values())
