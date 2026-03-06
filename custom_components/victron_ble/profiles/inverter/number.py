"""Template number entities for inverter profile."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricPotential
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ...bluetooth import VictronBluetooth
from ...const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up inverter template numbers."""
    if not entry.data.get("is_inverter", False):
        return
    async_add_entities([InverterSetpointNumberEntity(entry)])


class InverterSetpointNumberEntity(NumberEntity):
    """AC Voltage slider template (limits wired later)."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG
    _attr_name = "AC Voltage"
    _attr_native_min_value = 200.0
    _attr_native_max_value = 245.0
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_device_class = NumberDeviceClass.VOLTAGE
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.unique_id}_ac_voltage"
        self._attr_native_value = None
        self._unsub_dispatcher = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        address = self._entry.unique_id
        if not address:
            return
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass,
            VictronBluetooth.runtime_signal(address),
            self._handle_runtime_update,
        )
        self._refresh_from_runtime()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_dispatcher:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_runtime_update(self) -> None:
        self._refresh_from_runtime()
        self.async_write_ha_state()

    def _refresh_from_runtime(self) -> None:
        address = self._entry.unique_id
        if not address or not self.hass:
            return
        runtime = self.hass.data.get(VictronBluetooth.RUNTIME_KEY, {})
        reg_table = runtime.get(address, {}).get("register_table", {})

        slider_max = None
        slider_min = None
        value = None

        row = reg_table.get(VictronBluetooth.VE_REG_AC_OUT_VOLTAGE_SETPOINT)
        if isinstance(row, dict):
            value = row.get("value")

        row = reg_table.get(VictronBluetooth.VE_REG_AC_OUT_VOLTAGE_SETPOINT_MIN)
        if isinstance(row, dict):
            slider_min = row.get("value")

        row = reg_table.get(VictronBluetooth.VE_REG_AC_OUT_VOLTAGE_SETPOINT_MAX)
        if isinstance(row, dict):
            slider_max = row.get("value")

        if isinstance(slider_min, (int, float)):
            self._attr_native_min_value = float(slider_min)
        if isinstance(slider_max, (int, float)):
            self._attr_native_max_value = float(slider_max)
        if isinstance(value, (int, float)):
            self._attr_native_value = float(value)

    @property
    def device_info(self) -> DeviceInfo:
        address = self._entry.unique_id
        if address:
            return DeviceInfo(
                connections={(device_registry.CONNECTION_BLUETOOTH, address)},
                name=self._entry.title,
                manufacturer="Victron",
            )
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=self._entry.title,
            manufacturer="Victron",
        )

    async def async_set_native_value(self, value: float) -> None:
        """Template setter; write/apply logic will be added later."""
        normalized = round(float(value), 2)
        self._attr_native_value = normalized
        address = self._entry.unique_id
        if address and self.hass:
            runtime = self.hass.data.setdefault(VictronBluetooth.RUNTIME_KEY, {})
            device_runtime = runtime.setdefault(address, {})
            device_runtime["pending_setpoint"] = normalized
        self.async_write_ha_state()
