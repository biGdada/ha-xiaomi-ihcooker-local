"""Config and options flows for the Chunmi IH Cooker Slim."""

from __future__ import annotations

import re
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from miio import MiotDevice

from .const import (
    CONF_HOST,
    CONF_INFORMATION,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_TOKEN,
    CONF_USER_ID,
    DEFAULT_INFORMATION,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DEFAULT_USER_ID,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MAX_TIMEOUT,
    MIN_SCAN_INTERVAL,
    MIN_TIMEOUT,
    MODEL,
)
from .token_import import TokenCandidate, discover_tokens_sync

TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")
ATTR_CANDIDATE = "candidate"


def normalize_token(value: str) -> str:
    """Normalize a miIO token to 32 lowercase hex characters."""
    return value.strip().replace(" ", "").replace("-", "").lower()


def validate_device(host: str, token: str, timeout: int) -> Any:
    """Open a local miIO connection and return miIO.info()."""
    device = MiotDevice(
        ip=host,
        token=token,
        timeout=timeout,
        model=MODEL,
        mapping={"probe": {"siid": 1, "piid": 1}},
    )
    return device.info()


def _form_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the host/token form schema, optionally prefilled."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, "")): str,
            vol.Required(CONF_TOKEN, default=defaults.get(CONF_TOKEN, "")): str,
            vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)): str,
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=defaults.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(
                vol.Coerce(int),
                vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
            ),
            vol.Optional(
                CONF_TIMEOUT, default=defaults.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_TIMEOUT, max=MAX_TIMEOUT)),
        }
    )


class ChunmiIHConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a local miIO config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self._candidates: list[TokenCandidate] = []
        self._selected: TokenCandidate | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Let the user choose manual entry or token import."""
        return self.async_show_menu(
            step_id="user", menu_options=["manual", "import"]
        )

    async def async_step_manual(self, user_input: dict[str, Any] | None = None):
        """Enter host and token manually."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, result = await self._async_validate_and_create(user_input)
            if result is not None:
                return result
        return self.async_show_form(
            step_id="manual", data_schema=_form_schema(), errors=errors
        )

    async def async_step_import(self, user_input: dict[str, Any] | None = None):
        """Pick a token found in another Xiaomi integration."""
        errors: dict[str, str] = {}
        if not self._candidates:
            self._candidates = await self.hass.async_add_executor_job(
                discover_tokens_sync, self.hass
            )
        if not self._candidates:
            return self.async_abort(reason="no_tokens")

        if user_input is not None:
            key = user_input[ATTR_CANDIDATE]
            selected = next(
                (item for item in self._candidates if item.key == key), None
            )
            if selected is None:
                errors["base"] = "invalid_candidate"
            else:
                self._selected = selected
                return await self.async_step_import_details()

        labels = {item.key: item.label for item in self._candidates}
        return self.async_show_form(
            step_id="import",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        ATTR_CANDIDATE, default=next(iter(labels))
                    ): vol.In(labels)
                }
            ),
            errors=errors,
        )

    async def async_step_import_details(self, user_input: dict[str, Any] | None = None):
        """Confirm or correct the imported host/token."""
        if self._selected is None:
            return self.async_abort(reason="no_tokens")
        errors: dict[str, str] = {}
        if user_input is not None:
            errors, result = await self._async_validate_and_create(user_input)
            if result is not None:
                return result
        defaults = {
            CONF_HOST: self._selected.host or "",
            CONF_TOKEN: self._selected.token,
            CONF_NAME: self._selected.name or DEFAULT_NAME,
        }
        return self.async_show_form(
            step_id="import_details",
            data_schema=_form_schema(defaults),
            errors=errors,
        )

    async def _async_validate_and_create(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, str], Any | None]:
        """Validate a submitted form and create the entry on success."""
        errors: dict[str, str] = {}
        host = str(user_input[CONF_HOST]).strip()
        token = normalize_token(str(user_input[CONF_TOKEN]))
        timeout = int(user_input[CONF_TIMEOUT])
        if not TOKEN_RE.fullmatch(token):
            errors[CONF_TOKEN] = "invalid_token"
            return errors, None
        try:
            info = await self.hass.async_add_executor_job(
                validate_device, host, token, timeout
            )
        except Exception:  # noqa: BLE001 - miio exception hierarchy varies
            errors["base"] = "cannot_connect"
            return errors, None
        if getattr(info, "model", None) != MODEL:
            errors["base"] = "wrong_model"
            return errors, None

        identifier = (
            getattr(info, "mac_address", None) or f"{host}-{token[:8]}"
        ).replace(":", "").lower()
        await self.async_set_unique_id(identifier)
        self._abort_if_unique_id_configured()
        title = user_input.get(CONF_NAME) or DEFAULT_NAME
        data = {CONF_HOST: host, CONF_TOKEN: token, CONF_NAME: title}
        options = {
            CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
            CONF_TIMEOUT: timeout,
            CONF_USER_ID: DEFAULT_USER_ID,
            CONF_INFORMATION: DEFAULT_INFORMATION,
        }
        return {}, self.async_create_entry(title=title, data=data, options=options)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Return the options flow handler."""
        return ChunmiIHOptionsFlow(config_entry)


class ChunmiIHOptionsFlow(config_entries.OptionsFlow):
    """Options for polling and action metadata."""

    def __init__(self, config_entry) -> None:
        self._entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            token = normalize_token(self._entry.data.get(CONF_TOKEN, ""))
            host = self._entry.data[CONF_HOST]
            timeout = int(user_input[CONF_TIMEOUT])
            if not TOKEN_RE.fullmatch(token):
                errors["base"] = "invalid_token"
            else:
                try:
                    await self.hass.async_add_executor_job(
                        validate_device, host, token, timeout
                    )
                except Exception:  # noqa: BLE001
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(title="", data=user_input)

        current = self._entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                    vol.Optional(
                        CONF_TIMEOUT,
                        default=current.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                    ): vol.All(
                        vol.Coerce(int), vol.Range(min=MIN_TIMEOUT, max=MAX_TIMEOUT)
                    ),
                    vol.Optional(
                        CONF_USER_ID,
                        default=current.get(CONF_USER_ID, DEFAULT_USER_ID),
                    ): str,
                    vol.Optional(
                        CONF_INFORMATION,
                        default=current.get(CONF_INFORMATION, DEFAULT_INFORMATION),
                    ): str,
                }
            ),
            errors=errors,
        )
