"""Config flow for victron_ble integration."""
from __future__ import annotations

import logging
from collections.abc import Awaitable
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("Title"): str,
        vol.Required("key"): str,
    }
)


class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host = host

    async def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # TODO validate the data can be used to set up a connection.

    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data["username"], data["password"]
    # )

    hub = PlaceholderHub(data["host"])

    if not await hub.authenticate(data["username"], data["password"]):
        raise InvalidAuth

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth

    # Return info that you want to store in the config entry.
    return {"title": "Name of the device"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for victron_ble."""

    VERSION = 1

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle a flow initialized by bluetooth discovery."""
        _LOGGER.debug(discovery_info)
        self.context["discovery_info"] = {
            "name": discovery_info.name,
            "address": discovery_info.address,
        }
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """user setup."""
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

        # return await super().async_step_confirm(user_input)
        return self.async_create_entry(title=user_input["name"], data=user_input)

    async def async_step_unignore(self, user_input):
        unique_id = user_input["unique_id"]
        await self.async_set_unique_id(unique_id)
        self.async_abort(reason="discovery_error")

    # async def async_step_user(
    #     self, user_input: dict[str, Any] | None = None
    # ) -> FlowResult:
    #     """Handle the initial step."""
    #     _LOGGER.debug(f"IN HERE: {user_input}")
    #     if user_input is None:
    #         return self.async_show_form(
    #             step_id="user", data_schema=STEP_USER_DATA_SCHEMA
    #         )

    #     errors = {}

    #     try:
    #         info = await validate_input(self.hass, user_input)
    #     except CannotConnect:
    #         errors["base"] = "cannot_connect"
    #     except InvalidAuth:
    #         errors["base"] = "invalid_auth"
    #     except Exception:  # pylint: disable=broad-except
    #         _LOGGER.exception("Unexpected exception")
    #         errors["base"] = "unknown"
    #     else:
    #         return self.async_create_entry(title=info["title"], data=user_input)

    #     return self.async_show_form(
    #         step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
    #     )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
