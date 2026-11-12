from dataclasses import FrozenInstanceError

import pytest

from gatt_link_ble import (
    ConnectionMode,
    DeviceMetadata,
    GattDeviceState,
    GattSensorData,
)


def test_connection_modes_have_stable_values() -> None:
    assert ConnectionMode.PUSH.value == "push"
    assert ConnectionMode.POLL_AND_DISCONNECT.value == "poll_and_disconnect"


def test_device_state_defaults_and_nested_data_are_immutable() -> None:
    first = GattDeviceState(address="AA:BB")
    second = GattDeviceState(address="CC:DD")

    assert first.name is None
    assert first.metadata == DeviceMetadata()
    assert first.sensors == GattSensorData()
    assert first.supported_features == frozenset()
    assert first.metadata is not second.metadata
    assert first.sensors is not second.sensors
    with pytest.raises(FrozenInstanceError):
        first.address = "11:22"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        first.sensors.battery = 50  # type: ignore[misc]


def test_device_state_accepts_complete_sensor_and_metadata_values() -> None:
    state = GattDeviceState(
        address="AA:BB",
        name="sensor",
        metadata=DeviceMetadata(manufacturer="Nordic", model="Thingy"),
        sensors=GattSensorData(temperature=-12.45, battery=100),
        supported_features=frozenset({"temperature", "battery"}),
    )

    assert state.metadata.manufacturer == "Nordic"
    assert state.sensors.temperature == -12.45
    assert state.supported_features == frozenset({"temperature", "battery"})
