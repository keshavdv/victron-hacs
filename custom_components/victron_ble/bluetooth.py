"""Bluetooth ble helpers and protocol constants for Victron BLE."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional

from bleak import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.core import HomeAssistant as ha
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.exceptions import HomeAssistantError as ha_error

_LOGGER = logging.getLogger(__name__)


class VictronBluetooth:
    """BLE protocol constants and ble helpers."""

    INIT_UUID = "306b0002-b081-4037-83dc-e59fcc3cdfd0"
    CMD_INIT = [0xfa, 0x80, 0xff]
    # command 0xF980 important for receiving notification on uuid 306b0003
    CMD_INIT_NOTIFY = [0xf9, 0x80]

    # Characteristic UUID (hardcoded in the class)
    SERVICE_UUID = "306b0003-b081-4037-83dc-e59fcc3cdfd0"
    # command 0x0303 important for receiving notification
    CMD_ENABLE_NOTIFY = [0x03, 0x00, 0x03, 0x01, 0x03, 0x03]

    VE_DELIM = 0x19
    VE_LEN = 0x40

    CMD_VE_REG_GET_STR = [0x05, 0x00, 0x81] + [VE_DELIM]
    CMD_VE_REG_GET_INT = [0x05, 0x03, 0x81] + [VE_DELIM]
    CMD_VE_REG_SET     = [0x06, 0x03, 0x82] + [VE_DELIM]

    VE_REG_DEVICE_MODE = 0x0200
    VE_REG_AC_OUT_VOLTAGE_SETPOINT = 0x0230
    VE_REG_AC_OUT_VOLTAGE_SETPOINT_MIN = 0x0231
    VE_REG_AC_OUT_VOLTAGE_SETPOINT_MAX = 0x0232

    VE_REG_HISTORY_TIME = 0x1040
    VE_REG_HISTORY_ENERGY = 0x1041
    VE_REG_AC_OUT_CURRENT = 0x2201
    VE_REG_AC_OUT_VOLTAGE = 0x2200
    VE_REG_AC_OUT_APPARENT_POWER = 0x2205
    VE_REG_INV_LOOP_GET_IINV = 0xEB4E
    VE_REG_DC_CHANNEL1_VOLTAGE = 0xED8D
    VE_REG_BLUETOOTH_MAC_ADDRESS = 0xEC66
    VE_REG_BLUETOOTH_ENCRYPTION_KEY = 0xEC65

    REGISTER_SCALE_UNIT: dict[int, dict[str, float | str]] = {
        VE_REG_AC_OUT_VOLTAGE_SETPOINT:      {"scale": 0.01,  "unit": "V"},
        VE_REG_AC_OUT_VOLTAGE_SETPOINT_MIN:  {"scale": 0.01,  "unit": "V"},
        VE_REG_AC_OUT_VOLTAGE_SETPOINT_MAX:  {"scale": 0.01,  "unit": "V"},
        VE_REG_HISTORY_TIME:                 {"scale": 1.0,   "unit": "s"},
        VE_REG_HISTORY_ENERGY:               {"scale": 0.01,  "unit": "kVAh"},
        VE_REG_AC_OUT_CURRENT:               {"scale": 0.1,   "unit": "A"},
        VE_REG_AC_OUT_VOLTAGE:               {"scale": 0.01,  "unit": "V"},
        VE_REG_AC_OUT_APPARENT_POWER:        {"scale": 1.0,   "unit": "VA"},
        VE_REG_INV_LOOP_GET_IINV:            {"scale": 0.001, "unit": "A"},
        VE_REG_DC_CHANNEL1_VOLTAGE:          {"scale": 0.01,  "unit": "V"},
    }

    VE_REG_MODE_ON = 0x02
    VE_REG_MODE_OFF = 0x04
    VE_REG_MODE_ECO = 0x05

    MODE_TO_REGISTER_VALUE: dict[str, int] = {
        "on": VE_REG_MODE_ON,
        "eco": VE_REG_MODE_ECO,
        "off": VE_REG_MODE_OFF,
    }
    VERIFY_TIMEOUT_SECONDS = 20

    RUNTIME_KEY = "victron_ble_runtime"
    RUNTIME_UPDATED_SIGNAL = "victron_ble_runtime_updated"
    REQUESTED_REGISTERS: tuple[int, ...] = (
        VE_REG_DEVICE_MODE,
        VE_REG_AC_OUT_VOLTAGE_SETPOINT,
        VE_REG_AC_OUT_VOLTAGE_SETPOINT_MIN,
        VE_REG_AC_OUT_VOLTAGE_SETPOINT_MAX,
        VE_REG_INV_LOOP_GET_IINV,
        VE_REG_HISTORY_TIME,
        VE_REG_HISTORY_ENERGY,
    )

    busy_addresses: set[str] = set()

    def __init__(self, hass: ha, address: str) -> None:
        self.hass = hass
        self.address = address
        self.client: Optional[BleakClientWithServiceCache] = None
        self.register_table: dict[int, dict[str, Any]] = {}
        self._notify_initialized = False

    def is_connected(self) -> bool:
        return bool(self.client and self.client.is_connected)

    async def connect(self, timeout: int = 10) -> None:
        ble_device = async_ble_device_from_address(self.hass, self.address)
        if ble_device is None:
            raise ha_error(f"BLE device {self.address} not available")
        self.client = await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            self.address,
            timeout=timeout,
        )
        if self.is_connected():
            for service in self.client.services:
                for char in service.characteristics:
                    if "read" in char.properties:
                        # need to read properties to enable notification later
                        await self.client.read_gatt_char(char.uuid)

    async def disconnect(self) -> None:
        try:
            if self.is_connected():
                await self.client.disconnect()
                _LOGGER.debug("Disconnected from %s", self.address)
            self._notify_initialized = False
        except Exception as err:
            _LOGGER.error("Unexpected error with %s: %s", self.address, err)

    async def send_command(self, uuid: str, command: bytes | list[int]) -> bool:
        if not self.is_connected():
            _LOGGER.error("Not connected to inverter")
            return False
        try:
            command_bytes = bytes(command)
            _LOGGER.debug("Sending Command: %s", command_bytes.hex())
            await asyncio.wait_for(
                self.client.write_gatt_char(uuid, command_bytes, response=False),
                timeout=10,
            )
            await asyncio.sleep(0.2)
            return True
        except Exception as err:
            _LOGGER.error("Error sending command: %s", err)
            return False

    async def init_notify(self) -> None:
        if not self.is_connected():
            _LOGGER.error("Not connected to inverter")
            raise ha_error(f"Failed to initialize notifications for {self.address}")
        if self._notify_initialized:
            return

        try:
            _LOGGER.debug("Subscribing to notifications...")
            await self.client.start_notify(self.SERVICE_UUID, self.notification_handler)
            await self.send_command(self.INIT_UUID, self.CMD_INIT)
            await self.send_command(self.INIT_UUID, self.CMD_INIT_NOTIFY)
            await self.send_command(self.SERVICE_UUID, [0x01])
            await self.send_command(self.SERVICE_UUID, self.CMD_ENABLE_NOTIFY)
            self._notify_initialized = True

        except Exception as err:
            _LOGGER.error("Error during subscribe: %s", err)
            raise ha_error(f"Failed to initialize notifications for {self.address}")

    async def update_data(self, requested_registers) -> bool:
        # Force waiting for fresh values from current polling cycle.
        cmd = []
        for reg in requested_registers:
            self.register_table.pop(reg, None)
            cmd += self.CMD_VE_REG_GET_INT + self.reg_to_bytes(reg)

        try:
            ok = await self.send_command(self.SERVICE_UUID, cmd)
            if not ok:
                return False

            deadline = asyncio.get_running_loop().time() + 10
            while asyncio.get_running_loop().time() < deadline:
                missing = [reg for reg in requested_registers if reg not in self.register_table]
                if not missing:
                    return True
                await asyncio.sleep(0.1)

            missing_str = ", ".join(f"0x{reg:04X}" for reg in missing)
            _LOGGER.debug("Timeout waiting for registers: %s", missing_str)
            return False
        except Exception as err:
            _LOGGER.error("Error sending command: %s", err)
            return False

    def notification_handler(self, sender: int, data: bytearray) -> None:
        raw = bytes(data)
        if len(raw) < 6:
            return
        if raw[0] not in (0x08, 0x09):
            _LOGGER.debug("Notification: %s", data.hex())
            return
        if raw[0] == 0x09:
            return

        value_type = raw[1]
        delim = raw[2]
        register = int.from_bytes(raw[3:5], byteorder="big")
        data_length = raw[5] - self.VE_LEN
        if delim != self.VE_DELIM or data_length < 0:
            return

        data_start = 6
        data_end = data_start + data_length
        if data_end > len(raw):
            return

        value_bytes = raw[data_start:data_end]
        if value_type == 0x00:
            value: Any = value_bytes.hex()
            raw_value: Any = value
            _LOGGER.debug("Notification 0x%04X [str]: %s", register, value)
        elif value_type == 0x03:
            raw_value = int.from_bytes(value_bytes, byteorder="little")
            scale = float(self.REGISTER_SCALE_UNIT.get(register, {}).get("scale", 1.0))
            value = raw_value * scale
            _LOGGER.debug("Notification 0x%04X [num]: raw=%s scaled=%s", register, raw_value, value)
        else:
            value = value_bytes.hex()
            raw_value = value
            _LOGGER.debug("Unhandled value type 0x%02X for register 0x%04X: %s", value_type, register, value)

        self.register_table[register] = {
            "type": value_type,
            "raw": value_bytes.hex(),
            "raw_value": raw_value,
            "value": value,
        }

    @staticmethod
    def reg_to_bytes(register: int) -> list[int]:
        """Split 16-bit register into high and low byte."""
        return [(register >> 8) & 0xFF, register & 0xFF]

    @classmethod
    def runtime_signal(cls, address: str) -> str:
        return f"{cls.RUNTIME_UPDATED_SIGNAL}_{address}"

    @classmethod
    def build_set_command(cls, register: int, value: int, value_len: int = 1) -> bytes:
        if value_len <= 0:
            raise ValueError("value_len must be positive")
        payload = value.to_bytes(value_len, byteorder="little", signed=False)
        return bytes(cls.CMD_VE_REG_SET + cls.reg_to_bytes(register) + [cls.VE_LEN + value_len] + list(payload))

    @classmethod
    def build_device_mode_command(cls, mode: str) -> bytes:
        register_value = cls.MODE_TO_REGISTER_VALUE.get(mode)
        if register_value is None:
            raise ValueError(f"Unsupported mode: {mode}")
        return cls.build_set_command(cls.VE_REG_DEVICE_MODE, register_value, value_len=1)

    @classmethod
    def store_runtime(cls, hass: ha, address: str, register_table: dict[int, dict[str, Any]]) -> None:
        runtime = hass.data.setdefault(cls.RUNTIME_KEY, {})
        device_runtime = runtime.setdefault(address, {})
        device_runtime["register_table"] = dict(register_table)
        async_dispatcher_send(hass, cls.runtime_signal(address))

    @classmethod
    async def update(cls, hass: ha, address: str, ble: VictronBluetooth) -> None:
        await ble.init_notify()
        if await ble.update_data(cls.REQUESTED_REGISTERS):
            cls.store_runtime(hass, address, ble.register_table)

    @classmethod
    async def run(cls, hass: ha, address: str, action: Callable[[VictronBluetooth], Awaitable[None]]) -> None:
        if address in cls.busy_addresses:
            raise ha_error(f"Another command for {address} is already in progress")
        cls.busy_addresses.add(address)
        _LOGGER.debug("Establishing BLE connection to %s", address)
        ble = cls(hass, address)
        try:
            await ble.connect(timeout=10)
            _LOGGER.debug("Connected to %s", address)
            await action(ble)
        except Exception as err:
            if isinstance(err, asyncio.TimeoutError):
                raise ha_error(f"Timeout communicating with {address}")
            if isinstance(err, BleakError):
                raise ha_error(f"BLE error with {address}: {err}")
            raise ha_error(f"Unexpected BLE error with {address}: {err}")
        finally:
            await ble.disconnect()
            cls.busy_addresses.discard(address)

    @classmethod
    async def execute(cls, hass: ha, address: str, ble: VictronBluetooth, command: bytes | None = None) -> None:
        if command is not None:
            ok = await ble.send_command(cls.SERVICE_UUID, command)
            if not ok:
                raise ha_error(f"Failed sending command to {address}")
            _LOGGER.debug("Command sent to %s", address)

        await cls.update(hass, address, ble)

    @classmethod
    async def async_update(cls, hass: ha, address: str) -> None:
        async def action(ble: VictronBluetooth) -> None:
            await cls.execute(hass, address, ble, None)
        await cls.run(hass, address, action)

    @classmethod
    async def async_set_mode(cls, hass: ha, address: str, mode: str) -> None:
        """Build and send a mode command (on/off/eco)."""
        command = cls.build_device_mode_command(mode)
        await cls.async_send_command(hass, address, command)

    @classmethod
    async def async_send_command(cls, hass: ha, address: str, command: bytes) -> None:
        async def action(ble: VictronBluetooth) -> None:
            await cls.execute(hass, address, ble, command)
        await cls.run(hass, address, action)

    @classmethod
    async def async_setpoint_save(cls, hass: ha, address: str) -> None:
        """Send BLE command using HA bluetooth stack."""
        runtime = hass.data.get(cls.RUNTIME_KEY, {})
        device_runtime = runtime.get(address, {})
        value = device_runtime.get("pending_setpoint")
        if not isinstance(value, (int, float)):
            raise ha_error("Setpoint slider value is not available")
        scale = float(cls.REGISTER_SCALE_UNIT.get(cls.VE_REG_AC_OUT_VOLTAGE_SETPOINT, {}).get("scale", 1.0))
        raw_value = int(round(float(value) / scale))
        command = cls.build_set_command(cls.VE_REG_AC_OUT_VOLTAGE_SETPOINT, raw_value, value_len=2)
        await cls.async_send_command(hass, address, command)
