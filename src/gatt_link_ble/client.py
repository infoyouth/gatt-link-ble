"""Asynchronous BLE GATT client."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import fields, replace
from typing import TypedDict

from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    establish_connection,
)

from .const import DEVICE_INFORMATION_SERVICE_UUID
from .exceptions import GattConnectionError, GattParseError
from .models import (
    ConnectionMode,
    DeviceMetadata,
    GattDeviceState,
    GattSensorData,
)
from .parsers import DeviceInfoParser
from .parsers.base import BaseGattParser, normalize_uuid
from .registry import get_parsers_for_services

_LOGGER = logging.getLogger(__name__)

type BleDeviceSource = BLEDevice | Callable[[], BLEDevice]
type StateCallback = Callable[[GattDeviceState], None]
type DisconnectCallback = Callable[[], None]


class _SensorUpdates(TypedDict, total=False):
    temperature: float | None
    humidity: float | None
    pressure: float | None
    eco2: int | None
    tvoc: int | None
    battery: int | None
    illuminance: int | None


class GattLinkClient:
    """Read GATT sensor data by polling or maintain a notification connection."""

    def __init__(
        self,
        ble_device: BleDeviceSource,
        mode: ConnectionMode = ConnectionMode.PUSH,
        *,
        name: str | None = None,
        state_callback: StateCallback | None = None,
        disconnect_callback: DisconnectCallback | None = None,
    ) -> None:
        self._name_was_provided = name is not None
        if isinstance(ble_device, BLEDevice):
            self._ble_device = ble_device
            self._ble_device_callback: Callable[[], BLEDevice] | None = None
        else:
            self._ble_device_callback = ble_device
            self._ble_device = ble_device()

        self.mode = mode
        self.name = name or self._ble_device.name or self._ble_device.address
        self._state_callback = state_callback
        self._disconnect_callback = disconnect_callback
        self._state = GattDeviceState(
            address=self._ble_device.address,
            name=self._ble_device.name,
        )
        self._client: BleakClientWithServiceCache | None = None
        self._parsers: tuple[BaseGattParser, ...] = ()
        self._parser_by_characteristic: dict[str, BaseGattParser] = {}
        self._metadata_loaded = False
        self._running = False
        self._reconnect_task: asyncio.Task[None] | None = None

    @property
    def state(self) -> GattDeviceState:
        """Return the latest immutable device state."""
        return self._state

    async def start(self) -> None:
        """Connect and start notifications in PUSH mode."""
        if self.mode is not ConnectionMode.PUSH:
            raise ValueError("start() is only available in PUSH mode")
        if self._running:
            return

        self._running = True
        client: BleakClientWithServiceCache | None = None
        succeeded = False
        try:
            client = await self._establish_connection(self._on_disconnect)
            self._client = client
            await self._initialize(client)
            await self._start_notifications(client)
            await self._read_sensor_values(client, ignore_parse_errors=True)
            succeeded = True
        finally:
            if not succeeded:
                self._running = False
                self._client = None
                if client is not None:
                    await client.disconnect()

    async def stop(self) -> None:
        """Stop notifications and prevent automatic reconnection."""
        self._running = False
        reconnect_task = self._reconnect_task
        self._reconnect_task = None
        if reconnect_task is not None and reconnect_task is not asyncio.current_task():
            reconnect_task.cancel()
            try:
                await reconnect_task
            except asyncio.CancelledError:
                pass

        client = self._client
        self._client = None
        if client is not None:
            await client.disconnect()

    async def poll(self) -> GattDeviceState:
        """Connect, read available characteristics, and disconnect."""
        if self.mode is not ConnectionMode.POLL_AND_DISCONNECT:
            raise ValueError("poll() is only available in POLL_AND_DISCONNECT mode")

        client = await self._establish_connection()
        try:
            await self._initialize(client)
            await self._read_sensor_values(client, ignore_parse_errors=False)
            return self._state
        finally:
            await client.disconnect()

    async def _establish_connection(
        self,
        disconnected_callback: (
            Callable[[BleakClientWithServiceCache], None] | None
        ) = None,
    ) -> BleakClientWithServiceCache:
        try:
            return await establish_connection(
                BleakClientWithServiceCache,
                self._ble_device,
                self.name,
                disconnected_callback=disconnected_callback,
                max_attempts=3,
                ble_device_callback=self._ble_device_callback,
            )
        except BleakError as err:
            raise GattConnectionError(
                f"Unable to connect to {self._ble_device.address}: {err}"
            ) from err

    async def _initialize(self, client: BleakClientWithServiceCache) -> None:
        self._parsers = get_parsers_for_services(
            service.uuid for service in client.services.services.values()
        )
        self._parser_by_characteristic = {
            normalize_uuid(char_uuid): parser
            for parser in self._parsers
            for char_uuid in parser.characteristic_uuids
        }
        supported_features = frozenset(
            normalize_uuid(char_uuid)
            for parser in self._parsers
            if not isinstance(parser, DeviceInfoParser)
            for char_uuid in parser.characteristic_uuids
            if client.services.get_characteristic(char_uuid) is not None
        )
        self._set_state(replace(self._state, supported_features=supported_features))

        if not self._metadata_loaded:
            await self._read_device_metadata(client)

    async def _read_device_metadata(
        self,
        client: BleakClientWithServiceCache,
    ) -> None:
        parser = next(
            (
                item
                for item in self._parsers
                if item.service_uuid == DEVICE_INFORMATION_SERVICE_UUID
            ),
            None,
        )
        if parser is None:
            self._metadata_loaded = True
            return

        values: dict[str, str] = {}
        for char_uuid in parser.characteristic_uuids:
            characteristic = client.services.get_characteristic(char_uuid)
            if characteristic is None or "read" not in characteristic.properties:
                continue
            parsed = parser.parse_characteristic(
                char_uuid,
                await client.read_gatt_char(characteristic),
            )
            for field_name, value in parsed.items():
                if not isinstance(value, str):
                    raise GattParseError(
                        f"Device metadata parser returned a non-string {field_name}"
                    )
                values[field_name] = value

        current = self._state.metadata
        metadata = DeviceMetadata(
            manufacturer=values.get("manufacturer", current.manufacturer),
            model=values.get("model", current.model),
            firmware_revision=values.get(
                "firmware_revision",
                current.firmware_revision,
            ),
            hardware_revision=values.get(
                "hardware_revision",
                current.hardware_revision,
            ),
        )
        self._set_state(replace(self._state, metadata=metadata))
        self._metadata_loaded = True

    async def _start_notifications(
        self,
        client: BleakClientWithServiceCache,
    ) -> None:
        for parser in self._parsers:
            if isinstance(parser, DeviceInfoParser):
                continue
            for char_uuid in parser.characteristic_uuids:
                characteristic = client.services.get_characteristic(char_uuid)
                if characteristic is None:
                    continue
                properties = characteristic.properties
                if "notify" in properties or "indicate" in properties:
                    await client.start_notify(characteristic, self._on_notification)

    async def _read_sensor_values(
        self,
        client: BleakClientWithServiceCache,
        *,
        ignore_parse_errors: bool,
    ) -> None:
        for parser in self._parsers:
            if isinstance(parser, DeviceInfoParser):
                continue
            for char_uuid in parser.characteristic_uuids:
                characteristic = client.services.get_characteristic(char_uuid)
                if characteristic is None or "read" not in characteristic.properties:
                    continue
                data = await client.read_gatt_char(characteristic)
                self._parse_and_update(
                    parser,
                    char_uuid,
                    data,
                    ignore_parse_errors=ignore_parse_errors,
                )

    def _parse_and_update(
        self,
        parser: BaseGattParser,
        char_uuid: str,
        data: bytearray,
        *,
        ignore_parse_errors: bool,
    ) -> None:
        try:
            parsed = parser.parse_characteristic(char_uuid, data)
            sensor_fields = {field.name for field in fields(GattSensorData)}
            if not parsed.keys() <= sensor_fields:
                raise GattParseError(
                    "Parser returned unsupported sensor fields: "
                    f"{parsed.keys() - sensor_fields}"
                )
            updates: _SensorUpdates = {}
            for field_name, value in parsed.items():
                if field_name == "temperature" and (
                    isinstance(value, float) or value is None
                ):
                    updates["temperature"] = value
                elif field_name == "humidity" and (
                    isinstance(value, float) or value is None
                ):
                    updates["humidity"] = value
                elif field_name == "pressure" and (
                    isinstance(value, float) or value is None
                ):
                    updates["pressure"] = value
                elif field_name == "eco2" and (
                    isinstance(value, int) or value is None
                ):
                    updates["eco2"] = value
                elif field_name == "tvoc" and (
                    isinstance(value, int) or value is None
                ):
                    updates["tvoc"] = value
                elif field_name == "battery" and (
                    isinstance(value, int) or value is None
                ):
                    updates["battery"] = value
                elif field_name == "illuminance" and (
                    isinstance(value, int) or value is None
                ):
                    updates["illuminance"] = value
                else:
                    raise GattParseError(
                        f"Parser returned invalid value for sensor field {field_name}"
                    )
            sensors = replace(self._state.sensors, **updates)
        except GattParseError:
            if not ignore_parse_errors:
                raise
            _LOGGER.warning(
                "Unable to parse characteristic %s; retaining previous state",
                char_uuid,
                exc_info=True,
            )
            return

        self._set_state(replace(self._state, sensors=sensors))

    async def _on_notification(
        self,
        characteristic: BleakGATTCharacteristic,
        data: bytearray,
    ) -> None:
        char_uuid = normalize_uuid(characteristic.uuid)
        parser = self._parser_by_characteristic.get(char_uuid)
        if parser is None or isinstance(parser, DeviceInfoParser):
            _LOGGER.warning(
                "Received a notification for unregistered characteristic %s",
                char_uuid,
            )
            return
        self._parse_and_update(
            parser,
            char_uuid,
            data,
            ignore_parse_errors=True,
        )

    def _set_state(self, state: GattDeviceState) -> None:
        self._state = state
        if self._state_callback is not None:
            self._state_callback(state)

    def _on_disconnect(self, client: BleakClientWithServiceCache) -> None:
        if not self._running or client is not self._client:
            return
        self._client = None
        if self._reconnect_task is None or self._reconnect_task.done():
            self._reconnect_task = asyncio.create_task(self._reconnect())

    async def _reconnect(self) -> None:
        if self._disconnect_callback is not None:
            self._disconnect_callback()

        delay = 2
        while self._running:
            await asyncio.sleep(delay)
            if not self._running:
                return
            self._refresh_ble_device()

            client: BleakClientWithServiceCache | None = None
            try:
                client = await self._establish_connection(self._on_disconnect)
                if not self._running:
                    await client.disconnect()
                    return
                self._client = client
                await self._initialize(client)
                await self._start_notifications(client)
                await self._read_sensor_values(client, ignore_parse_errors=True)
                return
            except (BleakError, GattConnectionError, GattParseError):
                if client is not None:
                    await client.disconnect()
                _LOGGER.warning(
                    "Unable to reconnect to %s; retrying in %s seconds",
                    self._ble_device.address,
                    min(delay * 2, 60),
                    exc_info=True,
                )
                delay = min(delay * 2, 60)

    def _refresh_ble_device(self) -> None:
        if self._ble_device_callback is None:
            return

        self._ble_device = self._ble_device_callback()
        if not self._name_was_provided:
            self.name = self._ble_device.name or self._ble_device.address
        self._set_state(
            replace(
                self._state,
                address=self._ble_device.address,
                name=self._ble_device.name,
            )
        )
