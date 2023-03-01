import logging

from bluetooth_sensor_state_data import BluetoothData
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers.service_info.bluetooth import BluetoothServiceInfo
from sensor_state_data import SensorLibrary
from sensor_state_data.enum import StrEnum
from sensor_state_data.units import Units
from victron_ble.devices import detect_device_type
from victron_ble.devices.battery_monitor import AuxMode, BatteryMonitorData
from victron_ble.devices.battery_sense import BatterySenseData
from victron_ble.devices.dc_energy_meter import DcEnergyMeterData
from victron_ble.devices.solar_charger import SolarChargerData

_LOGGER = logging.getLogger(__name__)


class VictronSensor(StrEnum):
    AUX_MODE = "aux_mode"


class VictronBluetoothDeviceData(BluetoothData):
    """Data for Victron BLE sensors."""

    def __init__(self, key) -> None:
        """Initialize the class."""
        super().__init__()
        self.key = key

    def _start_update(self, service_info: BluetoothServiceInfo) -> None:
        """Update from BLE advertisement data."""
        _LOGGER.debug(
            "Parsing Victron BLE advertisement data: %s", service_info.manufacturer_data
        )
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
        parsed = device_parser(self.key).parse(data)
        _LOGGER.debug("Handle Victron BLE advertisement data: %s", parsed)
        self.set_device_type(parsed.get_model_name())

        if isinstance(parsed, DcEnergyMeterData):
            self.update_predefined_sensor(
                SensorLibrary.VOLTAGE__ELECTRIC_POTENTIAL_VOLT, parsed.get_voltage()
            )
            self.update_predefined_sensor(
                SensorLibrary.CURRENT__ELECTRIC_CURRENT_AMPERE, parsed.get_current()
            )
        elif isinstance(parsed, BatteryMonitorData):
            self.update_predefined_sensor(
                SensorLibrary.VOLTAGE__ELECTRIC_POTENTIAL_VOLT, parsed.get_voltage()
            )
            self.update_predefined_sensor(
                SensorLibrary.CURRENT__ELECTRIC_CURRENT_AMPERE, parsed.get_current()
            )
            self.update_predefined_sensor(
                SensorLibrary.BATTERY__PERCENTAGE, parsed.get_soc()
            )

            aux_mode = parsed.get_aux_mode()
            self.update_sensor(
                VictronSensor.AUX_MODE,
                None,
                parsed.get_aux_mode(),
                None,
                "Auxilliary Input Mode",
            )
            if aux_mode == AuxMode.MIDPOINT_VOLTAGE:
                self.update_sensor(
                    key="midpoint_voltage",
                    native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
                    native_value=parsed.get_midpoint_voltage(),
                    device_class=SensorDeviceClass.VOLTAGE,
                )
            elif aux_mode == AuxMode.STARTER_VOLTAGE:
                self.update_sensor(
                    key="starter_battery_voltage",
                    native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
                    native_value=parsed.get_starter_voltage(),
                    device_class=SensorDeviceClass.VOLTAGE,
                )
            elif aux_mode == AuxMode.TEMPERAUTRE:
                self.update_predefined_sensor(
                    SensorLibrary.TEMPERATURE__CELSIUS, parsed.get_temperature()
                )

        elif isinstance(parsed, BatterySenseData):
            self.update_predefined_sensor(
                SensorLibrary.TEMPERATURE__CELSIUS, parsed.get_temperature()
            )
            self.update_predefined_sensor(
                SensorLibrary.VOLTAGE__ELECTRIC_POTENTIAL_VOLT, parsed.get_voltage()
            )
        elif isinstance(parsed, SolarChargerData):
            self.update_predefined_sensor(
                SensorLibrary.POWER__POWER_WATT, parsed.get_solar_power()
            )
            self.update_predefined_sensor(
                SensorLibrary.VOLTAGE__ELECTRIC_POTENTIAL_VOLT,
                parsed.get_battery_voltage(),
            )
            self.update_predefined_sensor(
                SensorLibrary.CURRENT__ELECTRIC_CURRENT_AMPERE,
                parsed.get_battery_charging_current(),
            )
            self.update_predefined_sensor(
                SensorLibrary.ENERGY__ENERGY_KILO_WATT_HOUR, parsed.get_yield_today()
            )

            self.update_sensor(
                key="mode",
                native_unit_of_measurement=None,
                native_value=parsed.get_charge_state(),
                device_class=SensorDeviceClass.ENUM,
            )
            if parsed.get_external_device_load():
                self.update_sensor(
                    key="external_device_load",
                    native_unit_of_measurement=Units.ELECTRIC_CURRENT_AMPERE,
                    native_value=parsed.get_external_device_load(),
                    device_class=SensorDeviceClass.CURRENT,
                )
        return
