"""The victron_ble integration."""
from __future__ import annotations

import logging
from victron_ble.devices import detect_device_type
from victron_ble.devices.battery_monitor import BatteryMonitorData
from victron_ble.devices.dc_energy_meter import DcEnergyMeterData

from homeassistant.components.bluetooth import BluetoothScanningMode
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothProcessorCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from bluetooth_sensor_state_data import BluetoothData
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo

from sensor_state_data import SensorLibrary

from .const import DOMAIN

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)



class VictronBluetoothDeviceData(BluetoothData):
    """Data for Victron BLE sensors."""

    def _start_update(self, service_info: BluetoothServiceInfo) -> None:
        """Update from BLE advertisement data."""
        _LOGGER.debug("Parsing Victron BLE advertisement data: %s", service_info.manufacturer_data)
        manufacturer_data = service_info.manufacturer_data
        service_uuids = service_info.service_uuids
        local_name = service_info.name
        address = service_info.address
        self.set_device_name(local_name)
        self.set_device_manufacturer("Victron")

        self.set_precision(2)

        for mfr_id, mfr_data in manufacturer_data.items():
            if mfr_id != 0x02E1:
                continue
            self._process_mfr_data(address, local_name, mfr_id, mfr_data, service_uuids)

    def _process_mfr_data(
        self,
        address: str,
        local_name: str,
        mfr_id: int,
        data: bytes,
        service_uuids: list[str],
    ) -> None:

        """Parser for Victron sensors."""
        device_parser = detect_device_type(data)
        if not device_parser:
            _LOGGER.error("Could not identify Victron device type")
            return
        parsed = device_parser("aff4d0995b7d1e176c0c33ecb9e70dcd").parse(data)
        _LOGGER.debug("handle Victron BLE advertisement data: %s", parsed)

        if isinstance(parsed, DcEnergyMeterData):
            self.update_predefined_sensor(SensorLibrary.VOLTAGE__ELECTRIC_POTENTIAL_VOLT, parsed.get_voltage())
            self.update_predefined_sensor(SensorLibrary.CURRENT__ELECTRIC_CURRENT_AMPERE, parsed.get_current())
        elif isinstance(parsed, BatteryMonitorData):
            if parsed.get_temperature():
                self.update_predefined_sensor(SensorLibrary.TEMPERATURE__CELSIUS,  parsed.get_temperature())
            self.update_predefined_sensor(SensorLibrary.VOLTAGE__ELECTRIC_POTENTIAL_VOLT, parsed.get_voltage())
            self.update_predefined_sensor(SensorLibrary.CURRENT__ELECTRIC_CURRENT_AMPERE, parsed.get_current())
            self.update_predefined_sensor(SensorLibrary.BATTERY__PERCENTAGE, parsed.get_soc())
        return



async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Victron BLE device from a config entry."""
    address = entry.unique_id
    assert address is not None
    data = VictronBluetoothDeviceData()
    coordinator = hass.data.setdefault(DOMAIN, {})[
        entry.entry_id
    ] = PassiveBluetoothProcessorCoordinator(
        hass,
        _LOGGER,
        address=address,
        mode=BluetoothScanningMode.ACTIVE,
        update_method=data.update,
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(
        coordinator.async_start()
    )  # only start after all platforms have had a chance to subscribe
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
