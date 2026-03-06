"""Config flow for victron_ble integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from victron_ble.devices import detect_device_type
from victron_ble.devices.inverter import Inverter

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("Title"): str,
        vol.Required("key"): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):  # type: ignore[call-arg]
    """Handle a config flow for victron_ble."""

    VERSION = 1

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle a flow initialized by bluetooth discovery."""
        _LOGGER.debug(discovery_info)

        is_inverter = self._discovery_is_inverter(discovery_info)

        self.context["discovery_info"] = {
            "name": discovery_info.name,
            "address": discovery_info.address,
            "is_inverter": is_inverter,
        }

        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        return await self.async_step_user()

    def _discovery_is_inverter(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> bool:
        """Return True when discovered payload parses as InverterData."""

        manufacturer_data = discovery_info.manufacturer_data or {}

        for mfr_id, mfr_data in manufacturer_data.items():
            if mfr_id != 0x02E1 or not mfr_data.startswith(b"\x10"):
                continue

            parser = detect_device_type(mfr_data)
            if not parser:
                continue

            if parser is Inverter:
                return True

        return False

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """User setup."""
        if user_input is None:
            name = None
            address = None

            discovery_info = self.context.get("discovery_info")
            if discovery_info:
                name = self.context["discovery_info"]["name"]
                address = self.context["discovery_info"]["address"]

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required("name", default=name): str,
                        vol.Required("address", default=address): str,
                        vol.Required("key"): str,
                    }
                ),
            )

        await self.async_set_unique_id(user_input["address"])
        self._abort_if_unique_id_configured()

        entry_data = dict(user_input)
        discovery_info = self.context.get("discovery_info", {})
        entry_data["is_inverter"] = discovery_info.get("is_inverter", False)

        return self.async_create_entry(title=user_input["name"], data=entry_data)

    async def async_step_unignore(self, user_input):
        unique_id = user_input["unique_id"]
        await self.async_set_unique_id(unique_id)
        self.async_abort(reason="discovery_error")


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
