"""Thin wrapper around python-miio for the Chunmi IH Cooker Slim."""

from __future__ import annotations

import logging
from typing import Any

from miio import DeviceInfo, MiotDevice

from .const import (
    ACTION_ARGUMENT_PIIDS,
    ACTION_INTEGER_ARGUMENTS,
    ACTIONS,
    BOOLEAN_PROPERTIES,
    MIOT_ERROR_CODES,
    PROPERTIES,
    SUCCESS_CODES,
)
from .recipe import encode_gbk

_LOGGER = logging.getLogger(__name__)

MAX_PROPERTIES_PER_REQUEST = 10


class CookerError(Exception):
    """Base class for errors reported by the cooker."""


class CookerActionError(CookerError):
    """Raised when a MIoT action cannot be completed."""


class CookerPropertyError(CookerError):
    """Raised when a MIoT property cannot be read or written."""


def _result_code(result: Any) -> int | None:
    """Extract a MIoT result code from a python-miio response."""
    if isinstance(result, dict):
        code = result.get("code")
        return code if isinstance(code, int) else None
    if isinstance(result, list) and result:
        first = result[0]
        if isinstance(first, dict):
            code = first.get("code")
            return code if isinstance(code, int) else None
    return None


def _describe_code(code: int) -> str:
    return MIOT_ERROR_CODES.get(code, f"MIoT error {code}")


class IHCookerSlimDevice:
    """Local MIoT-over-miIO client for the cooker."""

    def __init__(
        self,
        host: str,
        token: str,
        *,
        timeout: int = 5,
        user_id: str = "uid_homeassistant",
        information: str = "info_030c01",
    ) -> None:
        self.host = host
        self.user_id = user_id
        self.information = information
        self._device = MiotDevice(
            ip=host,
            token=token,
            timeout=timeout,
            model="chunmi.ihcooker.slim",
            mapping=PROPERTIES,
        )

    def info(self) -> DeviceInfo:
        """Return miIO.info() data (model, mac, firmware versions)."""
        return self._device.info()

    def read_properties(self) -> dict[str, Any]:
        """Read every known property and return a key -> value mapping.

        Properties the device refuses to answer (with ``code: -4001``) are
        returned as ``None`` rather than causing the whole update to fail.
        """
        values: dict[str, Any] = {key: None for key in PROPERTIES}
        results = self._device.get_properties_for_mapping(
            max_properties=MAX_PROPERTIES_PER_REQUEST
        )
        for result in results:
            if not isinstance(result, dict):
                continue
            key = result.get("did")
            if key not in values:
                continue
            code = result.get("code", 0)
            if code not in SUCCESS_CODES:
                _LOGGER.debug("Property %s returned %s", key, _describe_code(code))
                continue
            values[key] = result.get("value")
        return values

    def set_property(self, key: str, value: Any) -> None:
        """Write a writable MIoT property, checking the returned result code."""
        if key not in PROPERTIES:
            raise CookerPropertyError(f"Unknown property: {key}")
        # The firmware requires JSON booleans, not 0/1 integers.
        if key in BOOLEAN_PROPERTIES:
            value = bool(value)
        try:
            result = self._device.set_property(key, value)
        except Exception as exc:  # noqa: BLE001 - miio raises several types
            raise CookerPropertyError(f"Could not write {key}: {exc}") from exc
        code = _result_code(result)
        if code is not None and code not in SUCCESS_CODES:
            raise CookerPropertyError(f"Could not write {key}: {_describe_code(code)}")

    def action(self, action: str, params: list[Any] | None = None) -> Any:
        """Call a MIoT action by its friendly name.

        The firmware expects each item in the action's ``in`` list to be an
        object containing ``piid`` and ``value``.  Sending bare values (as
        python-miio's convenience API does by default) makes the action parser
        reject the request with malformed JSON or ``-4003``.
        """
        if action not in ACTIONS:
            raise CookerActionError(f"Unknown action: {action}")
        siid, aiid = ACTIONS[action]
        values = list(params or [])
        piids = ACTION_ARGUMENT_PIIDS[action]
        if len(values) != len(piids):
            raise CookerActionError(
                f"Action {action} expects {len(piids)} argument(s), "
                f"got {len(values)}"
            )
        in_list = []
        for piid, value in zip(piids, values):
            if piid in ACTION_INTEGER_ARGUMENTS:
                try:
                    value = int(value)
                except (TypeError, ValueError) as exc:
                    raise CookerActionError(
                        f"Action {action} argument {piid} must be a number"
                    ) from exc
            else:
                value = str(value)
            in_list.append({"piid": piid, "value": value})
        try:
            result = self._device.call_action_by(siid, aiid, in_list)
        except Exception as exc:  # noqa: BLE001 - includes PayloadDecodeException
            raise CookerActionError(
                f"Action {action} ({siid}/{aiid}) failed: {exc}. "
                "Check the cooker state, pot placement and panel confirmation."
            ) from exc
        code = _result_code(result)
        if code is not None and code not in SUCCESS_CODES:
            raise CookerActionError(f"Action {action} failed: {_describe_code(code)}")
        return result

    # -- convenience wrappers --------------------------------------------
    def start_cook(self, cook_mode: int) -> Any:
        """Start one of the five built-in modes (service 2, action 1)."""
        return self.action("start_cook", [int(cook_mode)])

    def cancel_cooking(self) -> Any:
        return self.action("cancel_cooking")

    def pause(self) -> Any:
        return self.action("pause")

    def start_recipe(
        self, name: str, cook_data: str, *, name_gbk: str | None = None
    ) -> Any:
        """Start a custom recipe (service 3, action 1)."""
        encoded_name = name_gbk if name_gbk is not None else encode_gbk(name)
        return self.action("start_cooking", [encoded_name, cook_data, self.user_id])

    def start_cookcode(self, cookcode: str, name_gbk: str) -> Any:
        """Start a pre-normalized bundled cloud recipe.

        ``cookcode`` must already be the 160-byte runnable profile and
        ``name_gbk`` the plugin's GBK hex string with its trailing ``00``.
        Keeping this separate from :meth:`start_recipe` prevents accidental
        re-encoding of a cloud profile's name or CRC.
        """
        try:
            data = bytes.fromhex(cookcode)
        except ValueError as exc:
            raise CookerError("Recipe cookcode is not valid hex") from exc
        if len(data) != 160:
            raise CookerError(
                f"Recipe cookcode must be 160 bytes, got {len(data)}"
            )
        if not name_gbk or not name_gbk.endswith("00"):
            raise CookerError("Recipe name must be GBK hex ending in '00'")
        return self.start_recipe("", cookcode, name_gbk=name_gbk)

    def pause_cooking(self) -> Any:
        return self.action("pause_cooking", [self.information, self.user_id])

    def resume_paused(self) -> Any:
        return self.action("pause_recover", [self.information, self.user_id])

    def cancel_cooking_v2(self) -> Any:
        return self.action("cancel_cooking_v2", [self.information, self.user_id])

    def continue_cooking(self) -> Any:
        return self.action("continue_cooking", [self.information, self.user_id])

    def next_step(self) -> Any:
        return self.action("next_step_cooking", [self.information, self.user_id])

    def factory_reset(self) -> Any:
        return self.action("factory_reset", [self.information, self.user_id])

    def set_menu(self, name: str, cook_data: str, bell: bool = False) -> Any:
        """Save a recipe to one of the device menu slots (service 3, action 5)."""
        return self.action(
            "set_menu",
            [cook_data, self.user_id, int(bool(bell)), encode_gbk(name)],
        )

    def delete_menu(self, menu_order: int, bell: bool = False) -> Any:
        return self.action(
            "delete_menu",
            [self.user_id, self.information, int(bool(bell)), int(menu_order)],
        )

    def set_charge(self, charge_data: str) -> Any:
        return self.action("set_charge", [charge_data])

    def get_error_recorded(self, index: int) -> Any:
        return self.action("get_error_recorded", [int(index)])

    def get_selfcheck(self, command: int) -> Any:
        return self.action("get_selfcheck", [int(command)])
