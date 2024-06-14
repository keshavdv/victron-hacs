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
from victron_ble.devices.dcdc_converter import DcDcConverterData
from victron_ble.devices.inverter import InverterData
from victron_ble.devices.orion_xs import OrionXSData
from victron_ble.devices.solar_charger import SolarChargerData
from victron_ble.devices.vebus import VEBusData

_LOGGER = logging.getLogger(__name__)

def enum_to_native_value(e):
    return e.name.lower() if e is not None else None

class VictronSensor(StrEnum):
    AUX_MODE = "aux_mode"
    OPERATION_MODE = "operation_mode"
    EXTERNAL_DEVICE_LOAD = "external_device_load"
    YIELD_TODAY = "yield_today"
    INPUT_VOLTAGE = "input_voltage"
    OUTPUT_VOLTAGE = "output_voltage"
    INPUT_CURRENT = "input_current"
    OUTPUT_CURRENT = "output_current"
    OFF_REASON = "off_reason"
    CHARGER_ERROR = "charger_error"
    STARTER_BATTERY_VOLTAGE = "starter_battery_voltage"
    MIDPOINT_VOLTAGE = "midpoint_voltage"
    TIME_REMAINING = "time_remaining"
    BATTERY_VOLTAGE = "battery_voltage"
    BATTERY_CURRENT = "battery_current"
    BATTERY_TEMPERATURE = "battery_temperature"
    AC_VOLTAGE = "ac_voltage"
    AC_CURRENT = "ac_current"
    AC_APPARENT_POWER = "ac_apparent_power"
    AC_INPUT_STATE = "ac_input_state"
    AC_INPUT_POWER = "ac_input_power"
    AC_OUTPUT_POWER = "ac_output_power"
    ALARM_REASON = "alarm_reason"
    ALARM_NOTIFICATION = "alarm_notification"
    CONSUMED = "consumed"


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
            if mfr_id != 0x02E1 or not mfr_data.startswith(b"\x10"):
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
        _LOGGER.debug(f"Handle Victron BLE advertisement data: {parsed._data}")
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

            self.update_sensor(
                key=VictronSensor.TIME_REMAINING,
                name="Time remaining",
                native_unit_of_measurement=Units.TIME_MINUTES,
                native_value=parsed.get_remaining_mins(),
                device_class=SensorDeviceClass.DURATION,
            )

            self.update_sensor(
                key=VictronSensor.CONSUMED,
                name="Consumed",
                native_unit_of_measurement="Ah",
                native_value=parsed.get_consumed_ah(),
            )

            self.update_sensor(
                key=VictronSensor.ALARM_REASON,
                name="Alarm",
                native_unit_of_measurement=None,
                native_value=enum_to_native_value(parsed.get_alarm()),
                device_class=SensorDeviceClass.ENUM,
            )

            aux_mode = parsed.get_aux_mode()
            self.update_sensor(
                key=VictronSensor.AUX_MODE,
                name="Auxilliary Input Mode",
                native_unit_of_measurement=None,
                native_value=enum_to_native_value(aux_mode),
                device_class=SensorDeviceClass.ENUM,
            )
            if aux_mode == AuxMode.MIDPOINT_VOLTAGE:
                self.update_sensor(
                    key=VictronSensor.MIDPOINT_VOLTAGE,
                    native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
                    native_value=parsed.get_midpoint_voltage(),
                    device_class=SensorDeviceClass.VOLTAGE,
                )
            elif aux_mode == AuxMode.STARTER_VOLTAGE:
                self.update_sensor(
                    key=VictronSensor.STARTER_BATTERY_VOLTAGE,
                    native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
                    native_value=parsed.get_starter_voltage(),
                    device_class=SensorDeviceClass.VOLTAGE,
                )
            elif aux_mode == AuxMode.TEMPERATURE:
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
            self.update_sensor(
                key=VictronSensor.YIELD_TODAY,
                native_unit_of_measurement=Units.ENERGY_WATT_HOUR,
                native_value=parsed.get_yield_today(),
                device_class=SensorDeviceClass.CURRENT,
            )
            self.update_sensor(
                key=VictronSensor.OPERATION_MODE,
                native_unit_of_measurement=None,
                native_value=enum_to_native_value(parsed.get_charge_state()),
                device_class=SensorDeviceClass.ENUM,
            )
            if parsed.get_external_device_load():
                self.update_sensor(
                    key=VictronSensor.EXTERNAL_DEVICE_LOAD,
                    native_unit_of_measurement=Units.ELECTRIC_CURRENT_AMPERE,
                    native_value=parsed.get_external_device_load(),
                    device_class=SensorDeviceClass.CURRENT,
                )

        elif isinstance(parsed, DcDcConverterData):
            self.update_sensor(
                key=VictronSensor.OPERATION_MODE,
                native_unit_of_measurement=None,
                native_value=enum_to_native_value(parsed.get_charge_state()),
                device_class=SensorDeviceClass.ENUM,
            )
            self.update_sensor(
                key=VictronSensor.INPUT_VOLTAGE,
                native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
                native_value=parsed.get_input_voltage(),
                device_class=SensorDeviceClass.VOLTAGE,
            )
            self.update_sensor(
                key=VictronSensor.OUTPUT_VOLTAGE,
                native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
                native_value=parsed.get_output_voltage(),
                device_class=SensorDeviceClass.VOLTAGE,
            )
            self.update_sensor(
                key=VictronSensor.OFF_REASON,
                native_unit_of_measurement=None,
                native_value=enum_to_native_value(parsed.get_off_reason()),
                device_class=SensorDeviceClass.ENUM,
            )
            self.update_sensor(
                key=VictronSensor.CHARGER_ERROR,
                native_unit_of_measurement=None,
                native_value=enum_to_native_value(parsed.get_charger_error()),
                device_class=SensorDeviceClass.ENUM,
            )

        elif isinstance(parsed, InverterData):
            self.update_sensor(
                key=VictronSensor.OPERATION_MODE,
                native_unit_of_measurement=None,
                native_value=enum_to_native_value(parsed.get_device_state()),
                device_class=SensorDeviceClass.ENUM,
            )
            self.update_sensor(
                key=VictronSensor.BATTERY_VOLTAGE,
                native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
                native_value=parsed.get_battery_voltage(),
                device_class=SensorDeviceClass.VOLTAGE,
            )
            self.update_sensor(
                key=VictronSensor.AC_VOLTAGE,
                native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
                native_value=parsed.get_ac_voltage(),
                device_class=SensorDeviceClass.VOLTAGE,
            )
            self.update_sensor(
                key=VictronSensor.AC_CURRENT,
                native_unit_of_measurement=Units.ELECTRIC_CURRENT_AMPERE,
                native_value=parsed.get_ac_current(),
                device_class=SensorDeviceClass.CURRENT,
            )
            self.update_sensor(
                key=VictronSensor.AC_APPARENT_POWER,
                native_unit_of_measurement=Units.POWER_VOLT_AMPERE,
                native_value=parsed.get_ac_apparent_power(),
                device_class=SensorDeviceClass.APPARENT_POWER,
            )

        elif isinstance(parsed, OrionXSData):
            self.update_sensor(
                key=VictronSensor.OPERATION_MODE,
                native_unit_of_measurement=None,
                native_value=enum_to_native_value(parsed.get_charge_state()),
                device_class=SensorDeviceClass.ENUM,
            )
            self.update_sensor(
                key=VictronSensor.INPUT_VOLTAGE,
                native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
                native_value=parsed.get_input_voltage(),
                device_class=SensorDeviceClass.VOLTAGE,
            )
            self.update_sensor(
                key=VictronSensor.INPUT_CURRENT,
                native_unit_of_measurement=Units.ELECTRIC_CURRENT_AMPERE,
                native_value=parsed.get_input_current(),
                device_class=SensorDeviceClass.CURRENT,
            )
            self.update_sensor(
                key=VictronSensor.OUTPUT_VOLTAGE,
                native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
                native_value=parsed.get_output_voltage(),
                device_class=SensorDeviceClass.VOLTAGE,
            )
            self.update_sensor(
                key=VictronSensor.OUTPUT_CURRENT,
                native_unit_of_measurement=Units.ELECTRIC_CURRENT_AMPERE,
                native_value=parsed.get_output_current(),
                device_class=SensorDeviceClass.CURRENT,
            )
            self.update_sensor(
                key=VictronSensor.OFF_REASON,
                native_unit_of_measurement=None,
                native_value=enum_to_native_value(parsed.get_off_reason()),
                device_class=SensorDeviceClass.ENUM,
            )
            self.update_sensor(
                key=VictronSensor.CHARGER_ERROR,
                native_unit_of_measurement=None,
                native_value=enum_to_native_value(parsed.get_charger_error()),
                device_class=SensorDeviceClass.ENUM,
            )

        elif isinstance(parsed, VEBusData):
            self.update_sensor(
                key=VictronSensor.OPERATION_MODE,
                native_unit_of_measurement=None,
                native_value=enum_to_native_value(parsed.get_device_state()),
                device_class=SensorDeviceClass.ENUM,
            )
            self.update_sensor(
                key=VictronSensor.BATTERY_VOLTAGE,
                native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
                native_value=parsed.get_battery_voltage(),
                device_class=SensorDeviceClass.VOLTAGE,
            )
            self.update_sensor(
                key=VictronSensor.BATTERY_CURRENT,
                native_unit_of_measurement=Units.ELECTRIC_CURRENT_AMPERE,
                native_value=parsed.get_battery_current(),
                device_class=SensorDeviceClass.CURRENT,
            )
            self.update_sensor(
                key=VictronSensor.BATTERY_TEMPERATURE,
                native_unit_of_measurement=Units.TEMP_CELSIUS,
                native_value=parsed.get_battery_temperature(),
                device_class=SensorDeviceClass.TEMPERATURE,
            )
            self.update_predefined_sensor(
                SensorLibrary.BATTERY__PERCENTAGE, parsed.get_soc()
            )
            self.update_sensor(
                key=VictronSensor.AC_INPUT_STATE,
                native_unit_of_measurement=None,
                native_value=enum_to_native_value(parsed.get_ac_in_state()),
                device_class=SensorDeviceClass.ENUM,
            )
            self.update_sensor(
                key=VictronSensor.AC_INPUT_POWER,
                native_unit_of_measurement=Units.POWER_WATT,
                native_value=parsed.get_ac_in_power(),
                device_class=SensorDeviceClass.POWER,
            )
            self.update_sensor(
                key=VictronSensor.AC_OUTPUT_POWER,
                native_unit_of_measurement=Units.POWER_WATT,
                native_value=parsed.get_ac_out_power(),
                device_class=SensorDeviceClass.POWER,
            )
            self.update_sensor(
                key=VictronSensor.ALARM_NOTIFICATION,
                name="Alarm",
                native_unit_of_measurement=None,
                native_value=enum_to_native_value(parsed.get_alarm()),
                device_class=SensorDeviceClass.ENUM,
            )

        return
