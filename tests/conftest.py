from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from bleak.assigned_numbers import CharacteristicPropertyName
from bleak.backends.characteristic import (
    BleakGATTCharacteristic,
)
from bleak.backends.device import BLEDevice
from bleak.backends.service import BleakGATTService, BleakGATTServiceCollection
from bleak.uuids import normalize_uuid_str
from bleak_retry_connector import BleakClientWithServiceCache

from gatt_link_ble.const import (
    BATTERY_LEVEL_CHAR_UUID,
    BATTERY_SERVICE_UUID,
    DEVICE_INFORMATION_SERVICE_UUID,
    ENVIRONMENTAL_SENSING_SERVICE_UUID,
    FIRMWARE_REVISION_CHAR_UUID,
    HARDWARE_REVISION_CHAR_UUID,
    HEART_RATE_MEASUREMENT_CHAR_UUID,
    HEART_RATE_SERVICE_UUID,
    HUMIDITY_CHAR_UUID,
    MANUFACTURER_NAME_CHAR_UUID,
    MODEL_NUMBER_CHAR_UUID,
    PRESSURE_CHAR_UUID,
    TEMPERATURE_CHAR_UUID,
    THINGY_COLOR_CHAR_UUID,
    THINGY_ENVIRONMENT_SERVICE_UUID,
    THINGY_GAS_CHAR_UUID,
    THINGY_HUMIDITY_CHAR_UUID,
    THINGY_PRESSURE_CHAR_UUID,
    THINGY_TEMPERATURE_CHAR_UUID,
)

type ServiceCollectionFactory = Callable[
    [dict[str, list[CharacteristicPropertyName]]],
    MagicMock,
]
type ClientFactory = Callable[[MagicMock], MagicMock]

_SERVICE_BY_CHARACTERISTIC = {
    BATTERY_LEVEL_CHAR_UUID: BATTERY_SERVICE_UUID,
    FIRMWARE_REVISION_CHAR_UUID: DEVICE_INFORMATION_SERVICE_UUID,
    HARDWARE_REVISION_CHAR_UUID: DEVICE_INFORMATION_SERVICE_UUID,
    HEART_RATE_MEASUREMENT_CHAR_UUID: HEART_RATE_SERVICE_UUID,
    MANUFACTURER_NAME_CHAR_UUID: DEVICE_INFORMATION_SERVICE_UUID,
    MODEL_NUMBER_CHAR_UUID: DEVICE_INFORMATION_SERVICE_UUID,
    HUMIDITY_CHAR_UUID: ENVIRONMENTAL_SENSING_SERVICE_UUID,
    PRESSURE_CHAR_UUID: ENVIRONMENTAL_SENSING_SERVICE_UUID,
    TEMPERATURE_CHAR_UUID: ENVIRONMENTAL_SENSING_SERVICE_UUID,
    THINGY_GAS_CHAR_UUID: THINGY_ENVIRONMENT_SERVICE_UUID,
    THINGY_COLOR_CHAR_UUID: THINGY_ENVIRONMENT_SERVICE_UUID,
    THINGY_HUMIDITY_CHAR_UUID: THINGY_ENVIRONMENT_SERVICE_UUID,
    THINGY_PRESSURE_CHAR_UUID: THINGY_ENVIRONMENT_SERVICE_UUID,
    THINGY_TEMPERATURE_CHAR_UUID: THINGY_ENVIRONMENT_SERVICE_UUID,
}


@pytest.fixture
def ble_device() -> BLEDevice:
    return BLEDevice("AA:BB:CC:DD:EE:FF", "Test Device", {})


@pytest.fixture
def service_collection_factory() -> ServiceCollectionFactory:
    def build(
        characteristics: dict[str, list[CharacteristicPropertyName]],
    ) -> MagicMock:
        collection = MagicMock(spec=BleakGATTServiceCollection)
        services: dict[int, BleakGATTService] = {}
        services_by_uuid: dict[str, BleakGATTService] = {}
        characteristics_by_uuid: dict[str, BleakGATTCharacteristic] = {}
        for handle, service_uuid in enumerate(
            sorted({_SERVICE_BY_CHARACTERISTIC[uuid] for uuid in characteristics}),
            start=1,
        ):
            service = BleakGATTService(None, handle, service_uuid)
            services[handle] = service
            services_by_uuid[service_uuid] = service

        for handle, (char_uuid, properties) in enumerate(
            characteristics.items(),
            start=1,
        ):
            service = services_by_uuid[_SERVICE_BY_CHARACTERISTIC[char_uuid]]
            characteristic = BleakGATTCharacteristic(
                None,
                handle,
                char_uuid,
                properties,
                lambda: 20,
                service,
            )
            service.add_characteristic(characteristic)
            characteristics_by_uuid[char_uuid] = characteristic

        collection.services = services
        collection.get_characteristic = Mock(
            side_effect=lambda specifier: characteristics_by_uuid.get(
                normalize_uuid_str(str(specifier))
            )
        )
        return collection

    return build


@pytest.fixture
def client_factory() -> ClientFactory:
    def build(services: MagicMock) -> MagicMock:
        client = MagicMock(spec=BleakClientWithServiceCache)
        client.services = services
        client.read_gatt_char = AsyncMock(return_value=bytearray())
        client.start_notify = AsyncMock()
        client.disconnect = AsyncMock()
        return client

    return build
