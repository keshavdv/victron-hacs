"""Switch platform for Victron BLE inverter controls."""

from __future__ import annotations

from datetime import timedelta
import asyncio
import logging
from typing import Callable

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later, async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity

from ...bluetooth import VictronBluetooth
from ...const import DOMAIN

_LOGGER = logging.getLogger(__name__)
AUTO_UPDATE_INTERVAL = timedelta(minutes=10)
STARTUP_UPDATE_DELAY_SECONDS = 10.0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up inverter switches for inverter devices only."""
    if not entry.data.get("is_inverter", False):
        return

    async_add_entities([InverterAutoUpdateSwitchEntity(hass, entry)])


class InverterAutoUpdateSwitchEntity(RestoreEntity, SwitchEntity):
    """Auto-update switch that polls inverter values periodically."""

    _attr_has_entity_name = True
    _attr_name = "Auto Update"
    _attr_icon = "mdi:autorenew"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_auto_update"
        self._attr_is_on = False
        self._unsub_interval: Callable[[], None] | None = None
        self._unsub_startup_update: Callable[[], None] | None = None
        self._update_lock = asyncio.Lock()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None:
            _LOGGER.debug("Auto Update restore state is empty for %s", self._entry.unique_id)
            return
        if last_state.state == STATE_ON:
            self._attr_is_on = True
            self._start_auto_update()
            self.async_write_ha_state()
            self._schedule_startup_update()

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

    async def async_turn_on(self, **kwargs) -> None:
        """Enable periodic updates."""
        if self._attr_is_on:
            return
        self._attr_is_on = True
        self._start_auto_update()
        self.async_write_ha_state()
        await self._async_run_update("turn_on")

    async def async_turn_off(self, **kwargs) -> None:
        """Disable periodic updates."""
        if not self._attr_is_on:
            return
        self._attr_is_on = False
        self._stop_auto_update()
        self._cancel_startup_update()
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        self._stop_auto_update()
        self._cancel_startup_update()
        await super().async_will_remove_from_hass()

    def _start_auto_update(self) -> None:
        if self._unsub_interval is not None:
            return
        self._unsub_interval = async_track_time_interval(
            self._hass,
            self._handle_interval,
            AUTO_UPDATE_INTERVAL,
        )

    def _stop_auto_update(self) -> None:
        if self._unsub_interval is not None:
            self._unsub_interval()
            self._unsub_interval = None

    def _schedule_startup_update(self) -> None:
        self._cancel_startup_update()
        self._unsub_startup_update = async_call_later(
            self._hass,
            STARTUP_UPDATE_DELAY_SECONDS,
            self._handle_startup_update,
        )

    def _cancel_startup_update(self) -> None:
        if self._unsub_startup_update is not None:
            self._unsub_startup_update()
            self._unsub_startup_update = None

    @callback
    def _handle_interval(self, _now) -> None:
        if not self._attr_is_on:
            return
        self._hass.async_create_task(self._async_run_update("interval"))

    @callback
    def _handle_startup_update(self, _now) -> None:
        self._unsub_startup_update = None
        if not self._attr_is_on:
            return
        self._hass.async_create_task(self._async_run_update("restore_delayed"))

    async def _async_run_update(self, source: str) -> None:
        address = self._entry.unique_id
        if not address:
            return
        async with self._update_lock:
            try:
                _LOGGER.debug("Auto update (%s) for inverter %s", source, address)
                await VictronBluetooth.async_update(self._hass, address)
            except Exception as err:
                _LOGGER.error("Auto update failed for inverter %s: %s", address, err)
