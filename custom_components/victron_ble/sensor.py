"""Support for Victron ble sensors."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple, Union

from bluetooth_sensor_state_data import SIGNAL_STRENGTH_KEY
from homeassistant import config_entries
from homeassistant.components.bluetooth.passive_update_processor import (
    PassiveBluetoothDataProcessor,
    PassiveBluetoothDataUpdate,
    PassiveBluetoothEntityKey,
    PassiveBluetoothProcessorCoordinator,
    PassiveBluetoothProcessorEntity,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.sensor import sensor_device_info_to_hass_device_info
from sensor_state_data.data import SensorUpdate
from sensor_state_data.units import Units
from victron_ble.devices.base import ACInState, AlarmNotification, AlarmReason, ChargerError, OffReason, OperationMode
from victron_ble.devices.battery_monitor import AuxMode

from .const import DOMAIN
from .device import VictronSensor

_LOGGER = logging.getLogger(__name__)


SENSOR_DESCRIPTIONS: Dict[Tuple[SensorDeviceClass, Optional[Units]], Any] = {
    (SensorDeviceClass.TEMPERATURE, Units.TEMP_CELSIUS): SensorEntityDescription(
        key=f"{SensorDeviceClass.TEMPERATURE}_{Units.TEMP_CELSIUS}",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=Units.TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (SensorDeviceClass.VOLTAGE, Units.ELECTRIC_POTENTIAL_VOLT): SensorEntityDescription(
        key=f"{SensorDeviceClass.VOLTAGE}_{Units.ELECTRIC_POTENTIAL_VOLT}",
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (SensorDeviceClass.CURRENT, Units.ELECTRIC_CURRENT_AMPERE): SensorEntityDescription(
        key=f"{SensorDeviceClass.CURRENT}_{Units.ELECTRIC_CURRENT_AMPERE}",
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=Units.ELECTRIC_CURRENT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (SensorDeviceClass.BATTERY, Units.PERCENTAGE): SensorEntityDescription(
        key=f"{SensorDeviceClass.BATTERY}_{Units.PERCENTAGE}",
        device_class=SensorDeviceClass.BATTERY,
        native_unit_of_measurement=Units.PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (VictronSensor.YIELD_TODAY, Units.ENERGY_WATT_HOUR): SensorEntityDescription(
        key=VictronSensor.YIELD_TODAY,
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=Units.ENERGY_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    (SensorDeviceClass.POWER, Units.POWER_WATT): SensorEntityDescription(
        key=f"{SensorDeviceClass.POWER}_{Units.POWER_WATT}",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=Units.POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (VictronSensor.AUX_MODE, None): SensorEntityDescription(
        key=VictronSensor.AUX_MODE,
        device_class=SensorDeviceClass.ENUM,
        options=[x.lower() for x in AuxMode._member_names_],
    ),
    (VictronSensor.OPERATION_MODE, None): SensorEntityDescription(
        key=VictronSensor.OPERATION_MODE,
        device_class=SensorDeviceClass.ENUM,
        options=[x.lower() for x in OperationMode._member_names_],
    ),
    (VictronSensor.OFF_REASON, None): SensorEntityDescription(
        key=VictronSensor.OFF_REASON,
    ),
    (VictronSensor.CHARGER_ERROR, None): SensorEntityDescription(
        key=VictronSensor.CHARGER_ERROR,
        device_class=SensorDeviceClass.ENUM,
        options=[x.lower() for x in ChargerError._member_names_],
    ),
    (VictronSensor.ALARM_REASON, None): SensorEntityDescription(
        key=VictronSensor.ALARM_REASON,
    ),
    (VictronSensor.ALARM_NOTIFICATION, None): SensorEntityDescription(
        key=VictronSensor.ALARM_NOTIFICATION,
        device_class=SensorDeviceClass.ENUM,
        options=[x.lower() for x in AlarmNotification._member_names_],
    ),
    (VictronSensor.EXTERNAL_DEVICE_LOAD, Units.ELECTRIC_CURRENT_AMPERE): SensorEntityDescription(
        key=VictronSensor.EXTERNAL_DEVICE_LOAD,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=Units.ELECTRIC_CURRENT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (VictronSensor.TIME_REMAINING, Units.TIME_MINUTES): SensorEntityDescription(
        key=VictronSensor.TIME_REMAINING,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=Units.TIME_MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (VictronSensor.CONSUMED, "Ah"): SensorEntityDescription(
        key=VictronSensor.CONSUMED,
        native_unit_of_measurement="Ah",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (
        VictronSensor.INPUT_VOLTAGE,
        Units.ELECTRIC_POTENTIAL_VOLT,
    ): SensorEntityDescription(
        key=VictronSensor.INPUT_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (
        VictronSensor.OUTPUT_VOLTAGE,
        Units.ELECTRIC_POTENTIAL_VOLT,
    ): SensorEntityDescription(
        key=VictronSensor.OUTPUT_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (VictronSensor.INPUT_CURRENT, Units.ELECTRIC_CURRENT_AMPERE): SensorEntityDescription(
        key=VictronSensor.INPUT_CURRENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=Units.ELECTRIC_CURRENT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (VictronSensor.OUTPUT_CURRENT, Units.ELECTRIC_CURRENT_AMPERE): SensorEntityDescription(
        key=VictronSensor.OUTPUT_CURRENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=Units.ELECTRIC_CURRENT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (
        SIGNAL_STRENGTH_KEY,
        Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    ): SensorEntityDescription(
        key=f"{SensorDeviceClass.SIGNAL_STRENGTH}_{Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT}",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=Units.SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
    ),
    (
        VictronSensor.STARTER_BATTERY_VOLTAGE,
        Units.ELECTRIC_POTENTIAL_VOLT,
    ): SensorEntityDescription(
        key=VictronSensor.STARTER_BATTERY_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (
        VictronSensor.MIDPOINT_VOLTAGE,
        Units.ELECTRIC_POTENTIAL_VOLT,
    ): SensorEntityDescription(
        key=VictronSensor.MIDPOINT_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (VictronSensor.BATTERY_VOLTAGE, Units.ELECTRIC_POTENTIAL_VOLT): SensorEntityDescription(
        key=VictronSensor.BATTERY_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (VictronSensor.BATTERY_CURRENT, Units.ELECTRIC_CURRENT_AMPERE): SensorEntityDescription(
        key=VictronSensor.BATTERY_CURRENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=Units.ELECTRIC_CURRENT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (VictronSensor.BATTERY_TEMPERATURE, Units.TEMP_CELSIUS): SensorEntityDescription(
        key=VictronSensor.BATTERY_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=Units.TEMP_CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (VictronSensor.AC_VOLTAGE, Units.ELECTRIC_POTENTIAL_VOLT): SensorEntityDescription(
        key=VictronSensor.AC_VOLTAGE,
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=Units.ELECTRIC_POTENTIAL_VOLT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (VictronSensor.AC_CURRENT, Units.ELECTRIC_CURRENT_AMPERE): SensorEntityDescription(
        key=VictronSensor.AC_CURRENT,
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=Units.ELECTRIC_CURRENT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (VictronSensor.AC_APPARENT_POWER, Units.POWER_VOLT_AMPERE): SensorEntityDescription(
        key=VictronSensor.AC_CURRENT,
        device_class=SensorDeviceClass.APPARENT_POWER,
        native_unit_of_measurement=Units.POWER_VOLT_AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (VictronSensor.AC_INPUT_STATE, None): SensorEntityDescription(
        key=VictronSensor.AC_INPUT_STATE,
        device_class=SensorDeviceClass.ENUM,
        options=[x.lower() for x in ACInState._member_names_],
    ),
    (VictronSensor.AC_INPUT_POWER, Units.POWER_WATT): SensorEntityDescription(
        key=VictronSensor.AC_INPUT_POWER,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=Units.POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    (VictronSensor.AC_OUTPUT_POWER, Units.POWER_WATT): SensorEntityDescription(
        key=VictronSensor.AC_OUTPUT_POWER,
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=Units.POWER_WATT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
}


def sensor_update_to_bluetooth_data_update(
    sensor_update: SensorUpdate,
) -> PassiveBluetoothDataUpdate:
    """Convert a sensor update to a bluetooth data update."""
    data = PassiveBluetoothDataUpdate(
        devices={
            device_id: sensor_device_info_to_hass_device_info(device_info)
            for device_id, device_info in sensor_update.devices.items()
        },
        entity_descriptions={
            PassiveBluetoothEntityKey(
                device_key.key, device_key.device_id
            ): SENSOR_DESCRIPTIONS[
                (description.device_key.key, description.native_unit_of_measurement)
            ]
            for device_key, description in sensor_update.entity_descriptions.items()
            if description.device_key
        },
        entity_data={
            PassiveBluetoothEntityKey(
                device_key.key, device_key.device_id
            ): sensor_values.native_value
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
        entity_names={
            PassiveBluetoothEntityKey(
                device_key.key, device_key.device_id
            ): sensor_values.name
            for device_key, sensor_values in sensor_update.entity_values.items()
        },
    )
    _LOGGER.debug(f"IN 2here: {data}")

    return data


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Victron BLE sensors."""
    coordinator: PassiveBluetoothProcessorCoordinator = hass.data[DOMAIN][
        entry.entry_id
    ]
    processor = PassiveBluetoothDataProcessor(sensor_update_to_bluetooth_data_update)
    entry.async_on_unload(
        processor.async_add_entities_listener(
            VictronBluetoothSensorEntity, async_add_entities
        )
    )
    entry.async_on_unload(coordinator.async_register_processor(processor))


class VictronBluetoothSensorEntity(
    PassiveBluetoothProcessorEntity[
        PassiveBluetoothDataProcessor[float | int | None, SensorUpdate],
    ],
    SensorEntity,
):
    """Representation of a Victron device that emits Instant Readout advertisements."""

    @property
    def native_value(self) -> int | float | None:
        """Return the native value."""
        return self.processor.entity_data.get(self.entity_key)
