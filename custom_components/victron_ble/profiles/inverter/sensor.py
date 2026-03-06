"""Template diagnostic sensors for inverter profile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers import device_registry
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from ...bluetooth import VictronBluetooth
from ...const import DOMAIN


@dataclass(frozen=True)
class InverterDiagnosticSensorDescription:
    """Description for inverter diagnostic sensor template."""

    key: str
    name: str
    unit: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    options: list[str] | None = None
    register: int | None = None
    category: EntityCategory  | None = None


SENSOR_DESCRIPTIONS: tuple[InverterDiagnosticSensorDescription, ...] = (
    InverterDiagnosticSensorDescription(
        key="ac_voltage_setpoint",
        name="AC Voltage Setpoint",
        unit=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        register=VictronBluetooth.VE_REG_AC_OUT_VOLTAGE_SETPOINT,
        category=EntityCategory.DIAGNOSTIC
    ),
    InverterDiagnosticSensorDescription(
        key="device_mode",
        name="Device Mode",
        device_class=SensorDeviceClass.ENUM,
        options=["On", "Off", "Eco"],
        register=VictronBluetooth.VE_REG_DEVICE_MODE,
        category=EntityCategory.DIAGNOSTIC
    ),
    InverterDiagnosticSensorDescription(
        key="running_time",
        name="Running Time",
        unit=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        register=VictronBluetooth.VE_REG_HISTORY_TIME,
        category=EntityCategory.DIAGNOSTIC
    ),
    InverterDiagnosticSensorDescription(
        key="generated_energy",
        name="Generated enegry",
        unit="kVAh",
        state_class=SensorStateClass.MEASUREMENT,
        register=VictronBluetooth.VE_REG_HISTORY_ENERGY,
        category=EntityCategory.DIAGNOSTIC
    ),
    InverterDiagnosticSensorDescription(
        key="inverter_loop_current",
        name="Inverter Loop Current",
        unit=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        register=VictronBluetooth.VE_REG_INV_LOOP_GET_IINV,
        category=EntityCategory.DIAGNOSTIC
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up inverter diagnostic template sensors."""
    if not entry.data.get("is_inverter", False):
        return

    async_add_entities(
        InverterDiagnosticSensorEntity(entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class InverterDiagnosticSensorEntity(SensorEntity):
    """Diagnostic inverter sensor template (data binding added later)."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, description: InverterDiagnosticSensorDescription) -> None:
        self._entry = entry
        self._description = description
        self._unsub_dispatcher = None
        self._attr_entity_category = description.category

        self.entity_description = SensorEntityDescription(
            key=description.key,
            name=description.name,
            native_unit_of_measurement=description.unit,
            device_class=description.device_class,
            state_class=description.state_class,
            options=description.options,
        )
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._native_value: Any = None

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
        register = self._description.register
        if register is None:
            return
        row = reg_table.get(register)
        if not isinstance(row, dict):
            return

        if register == VictronBluetooth.VE_REG_DEVICE_MODE:
            raw = row.get("value")
            mode_map = {
                VictronBluetooth.VE_REG_MODE_ON: "On",
                VictronBluetooth.VE_REG_MODE_OFF: "Off",
                VictronBluetooth.VE_REG_MODE_ECO: "Eco",
            }
            self._native_value = mode_map.get(raw)
            return

        value = row.get("value")
        if isinstance(value, (int, float)):
            if register == VictronBluetooth.VE_REG_HISTORY_TIME:
                self._native_value = round(float(value) / 3600.0, 2)
            else:
                self._native_value = value

    @property
    def native_value(self) -> Any:
        """Current value placeholder."""
        return self._native_value

    @property
    def available(self) -> bool:
        """Template entities are available, values will be wired later."""
        return True

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
