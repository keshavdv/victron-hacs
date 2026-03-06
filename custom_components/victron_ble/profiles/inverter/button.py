"""Button platform for Victron BLE inverter controls."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ...bluetooth import VictronBluetooth
from ...const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class InverterButtonDescription:
    """Button description for inverter control."""

    key: str
    name: str
    icon: str
    mode: str | None = None
    action: str = "set_mode"
    category: EntityCategory  | None = None


BUTTONS: tuple[InverterButtonDescription, ...] = (
    InverterButtonDescription(
        key="inverter_on",
        name="Inverter On",
        icon="mdi:power-plug",
        mode="on",
    ),
    InverterButtonDescription(
        key="inverter_eco",
        name="Inverter Eco",
        icon="mdi:leaf",
        mode="eco",
    ),
    InverterButtonDescription(
        key="inverter_off",
        name="Inverter Off",
        icon="mdi:power-plug-off",
        mode="off",
    ),
    InverterButtonDescription(
        key="inverter_update_values",
        name="Update Values",
        icon="mdi:refresh",
        action="update_values",
        category=EntityCategory.DIAGNOSTIC
    ),
    InverterButtonDescription(
        key="inverter_setpoint_save",
        name="AC Voltage Apply",
        icon="mdi:refresh",
        action="setpoint_save",
        category=EntityCategory.CONFIG
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up inverter control buttons for inverter devices only."""
    if not entry.data.get("is_inverter", False):
        return

    async_add_entities(
        VictronInverterButtonEntity(hass, entry, description)
        for description in BUTTONS
    )


class VictronInverterButtonEntity(ButtonEntity):
    """Button entity that sends BLE inverter commands."""

    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, description: InverterButtonDescription) -> None:
        self._hass = hass
        self._entry = entry
        self._description = description
        self._attr_name = description.name
        self._attr_icon = description.icon
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        if description.category:
            self._attr_entity_category = description.category

        self._press_lock = asyncio.Lock()
        self._is_busy = False

    @property
    def icon(self) -> str:
        """Return dynamic icon while command is in progress."""
        if self._is_busy:
            return "mdi:progress-clock"
        return self._description.icon

    @property
    def extra_state_attributes(self) -> dict[str, bool]:
        """Expose command execution state."""
        return {"in_progress": self._is_busy}

    @property
    def available(self) -> bool:
        """Disable button while command exchange is in progress."""
        return not self._is_busy

    @property
    def device_info(self) -> DeviceInfo:
        address = self._entry.unique_id

        if address:
            return DeviceInfo(
                connections={(dr.CONNECTION_BLUETOOTH, address)},
                name=self._entry.title,
                manufacturer="Victron",
            )

        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title,
            manufacturer="Victron",
        )

    async def async_press(self) -> None:
        """Handle button press."""
        if self._press_lock.locked():
            raise HomeAssistantError("Command is already in progress")

        address = self._entry.unique_id

        if not address:
            raise ValueError("Missing BLE address in config entry")

        async with self._press_lock:
            self._is_busy = True
            self.async_write_ha_state()
            try:
                _LOGGER.debug("Sending command '%s' to inverter %s", self._description.key, address)
                if self._description.action == "set_mode" and self._description.mode:
                    await VictronBluetooth.async_set_mode(self._hass, address, self._description.mode)
                elif self._description.action == "update_values":
                    await VictronBluetooth.async_update(self._hass, address)
                elif self._description.action == "setpoint_save":
                    await VictronBluetooth.async_setpoint_save(self._hass, address)
            finally:
                self._is_busy = False
                self.async_write_ha_state()
