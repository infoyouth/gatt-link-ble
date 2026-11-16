import asyncio
import struct
from collections.abc import Callable
from datetime import UTC
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from bleak.assigned_numbers import CharacteristicPropertyName
from bleak.backends.characteristic import BleakGATTCharacteristic
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache

from gatt_link_ble import ConnectionMode, GattLinkClient
from gatt_link_ble.const import (
    BATTERY_LEVEL_CHAR_UUID,
    BATTERY_SERVICE_UUID,
    FIRMWARE_REVISION_CHAR_UUID,
    HEART_RATE_MEASUREMENT_CHAR_UUID,
    HUMIDITY_CHAR_UUID,
    MANUFACTURER_NAME_CHAR_UUID,
    MODEL_NUMBER_CHAR_UUID,
    PRESSURE_CHAR_UUID,
    TEMPERATURE_CHAR_UUID,
    THINGY_COLOR_CHAR_UUID,
    THINGY_GAS_CHAR_UUID,
    THINGY_HUMIDITY_CHAR_UUID,
    THINGY_PRESSURE_CHAR_UUID,
    THINGY_TEMPERATURE_CHAR_UUID,
)
from gatt_link_ble.exceptions import (
    GattConnectionError,
    GattParseError,
    GattTimeoutError,
)

type ServiceCollectionFactory = Callable[
    [dict[str, list[CharacteristicPropertyName]]],
    MagicMock,
]
type ClientFactory = Callable[[MagicMock], MagicMock]


@pytest.mark.asyncio
async def test_poll_reads_metadata_and_sensors_then_disconnects(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = service_collection_factory(
        {
            BATTERY_LEVEL_CHAR_UUID: ["read"],
            MANUFACTURER_NAME_CHAR_UUID: ["read"],
            MODEL_NUMBER_CHAR_UUID: ["read"],
            FIRMWARE_REVISION_CHAR_UUID: ["read"],
            TEMPERATURE_CHAR_UUID: ["read"],
            PRESSURE_CHAR_UUID: ["read"],
        }
    )
    client = client_factory(services)
    payloads = {
        BATTERY_LEVEL_CHAR_UUID: bytearray(b"\x64"),
        MANUFACTURER_NAME_CHAR_UUID: bytearray(b"Nordic"),
        MODEL_NUMBER_CHAR_UUID: bytearray(b"Thingy"),
        FIRMWARE_REVISION_CHAR_UUID: bytearray(b"1.2"),
        TEMPERATURE_CHAR_UUID: bytearray(struct.pack("<h", -1245)),
        PRESSURE_CHAR_UUID: bytearray(struct.pack("<I", 1_013_250)),
    }

    async def read_characteristic(
        characteristic: BleakGATTCharacteristic,
    ) -> bytearray:
        return payloads[characteristic.uuid]

    client.read_gatt_char.side_effect = read_characteristic
    establish = AsyncMock(side_effect=[client, client])
    monkeypatch.setattr("gatt_link_ble.client.establish_connection", establish)
    provider = Mock(return_value=ble_device)
    gatt_client = GattLinkClient(
        provider,
        ConnectionMode.POLL_AND_DISCONNECT,
    )

    state = await gatt_client.poll()
    await gatt_client.poll()

    assert state.address == "AA:BB:CC:DD:EE:FF"
    assert state.metadata.manufacturer == "Nordic"
    assert state.metadata.model == "Thingy"
    assert state.metadata.firmware_revision == "1.2"
    assert state.sensors.battery == 100
    assert state.sensors.temperature == -12.45
    assert state.sensors.pressure == 1013.25
    assert BATTERY_LEVEL_CHAR_UUID in state.supported_features
    connection_args = establish.await_args
    assert connection_args is not None
    assert connection_args.kwargs["max_attempts"] == 3
    assert connection_args.args[1] is ble_device
    assert connection_args.kwargs["timeout"] == 10.0
    assert (
        sum(
            call.args[0].uuid == MANUFACTURER_NAME_CHAR_UUID
            for call in client.read_gatt_char.await_args_list
        )
        == 1
    )
    assert client.disconnect.await_count == 2


@pytest.mark.asyncio
async def test_poll_updates_heart_rate_sensor(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = service_collection_factory({HEART_RATE_MEASUREMENT_CHAR_UUID: ["read"]})
    client = client_factory(services)
    client.read_gatt_char.return_value = bytearray(struct.pack("<BB", 0, 72))
    establish = AsyncMock(return_value=client)
    monkeypatch.setattr("gatt_link_ble.client.establish_connection", establish)
    gatt_client = GattLinkClient(ble_device, ConnectionMode.POLL_AND_DISCONNECT)

    state = await gatt_client.poll()

    assert state.sensors.heart_rate == 72
    assert HEART_RATE_MEASUREMENT_CHAR_UUID in state.supported_features


@pytest.mark.asyncio
async def test_poll_continues_after_a_characteristic_read_fails(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    services = service_collection_factory(
        {
            BATTERY_LEVEL_CHAR_UUID: ["read"],
            TEMPERATURE_CHAR_UUID: ["read"],
        }
    )
    client = client_factory(services)

    async def read_characteristic(
        characteristic: BleakGATTCharacteristic,
    ) -> bytearray:
        if characteristic.uuid == BATTERY_LEVEL_CHAR_UUID:
            raise BleakError("battery read failed")
        return bytearray(struct.pack("<h", 2050))

    client.read_gatt_char.side_effect = read_characteristic
    monkeypatch.setattr(
        "gatt_link_ble.client.establish_connection",
        AsyncMock(return_value=client),
    )
    gatt_client = GattLinkClient(
        ble_device,
        ConnectionMode.POLL_AND_DISCONNECT,
    )

    state = await gatt_client.poll()

    assert state.sensors.temperature == 20.5
    assert state.sensors.battery is None
    assert "battery read failed" in caplog.text
    assert state.last_updated.tzinfo is UTC
    diagnostics = gatt_client.get_diagnostics()
    assert diagnostics["failed_characteristics"] == [BATTERY_LEVEL_CHAR_UUID]
    assert diagnostics["last_error"] == "battery read failed"
    client.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_poll_continues_after_device_metadata_read_fails(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    services = service_collection_factory(
        {
            BATTERY_LEVEL_CHAR_UUID: ["read"],
            MANUFACTURER_NAME_CHAR_UUID: ["read"],
            MODEL_NUMBER_CHAR_UUID: ["read"],
        }
    )
    client = client_factory(services)

    async def read_characteristic(
        characteristic: BleakGATTCharacteristic,
    ) -> bytearray:
        if characteristic.uuid == MANUFACTURER_NAME_CHAR_UUID:
            raise BleakError("manufacturer read failed")
        if characteristic.uuid == MODEL_NUMBER_CHAR_UUID:
            return bytearray(b"Thingy")
        return bytearray(b"\x40")

    client.read_gatt_char.side_effect = read_characteristic
    monkeypatch.setattr(
        "gatt_link_ble.client.establish_connection",
        AsyncMock(return_value=client),
    )
    gatt_client = GattLinkClient(
        ble_device,
        ConnectionMode.POLL_AND_DISCONNECT,
    )

    state = await gatt_client.poll()

    assert state.metadata.manufacturer is None
    assert state.metadata.model == "Thingy"
    assert state.sensors.battery == 64
    assert "manufacturer read failed" in caplog.text


@pytest.mark.asyncio
async def test_poll_raises_connection_error_when_all_characteristic_reads_fail(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = service_collection_factory({BATTERY_LEVEL_CHAR_UUID: ["read"]})
    client = client_factory(services)
    client.read_gatt_char.side_effect = BleakError("device unavailable")
    monkeypatch.setattr(
        "gatt_link_ble.client.establish_connection",
        AsyncMock(return_value=client),
    )
    gatt_client = GattLinkClient(
        ble_device,
        ConnectionMode.POLL_AND_DISCONNECT,
    )

    with pytest.raises(GattConnectionError, match="any available"):
        await gatt_client.poll()

    client.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_enabled_capabilities_filter_push_reads_and_subscriptions(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = service_collection_factory(
        {
            BATTERY_LEVEL_CHAR_UUID: ["read", "notify"],
            HUMIDITY_CHAR_UUID: ["read", "notify"],
            TEMPERATURE_CHAR_UUID: ["read", "notify"],
        }
    )
    client = client_factory(services)
    client.read_gatt_char.return_value = bytearray(struct.pack("<h", 2050))
    monkeypatch.setattr(
        "gatt_link_ble.client.establish_connection",
        AsyncMock(return_value=client),
    )
    gatt_client = GattLinkClient(
        ble_device,
        enabled_capabilities={"temperature"},
    )

    await gatt_client.start()

    read_uuids = {call.args[0].uuid for call in client.read_gatt_char.await_args_list}
    notify_uuids = {call.args[0].uuid for call in client.start_notify.await_args_list}
    assert read_uuids == {TEMPERATURE_CHAR_UUID}
    assert notify_uuids == {TEMPERATURE_CHAR_UUID}
    assert gatt_client.state.supported_features == frozenset(
        {BATTERY_LEVEL_CHAR_UUID, HUMIDITY_CHAR_UUID, TEMPERATURE_CHAR_UUID}
    )
    await gatt_client.stop()


@pytest.mark.asyncio
async def test_empty_capability_set_disables_sensor_io(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = service_collection_factory({BATTERY_LEVEL_CHAR_UUID: ["read", "notify"]})
    client = client_factory(services)
    monkeypatch.setattr(
        "gatt_link_ble.client.establish_connection",
        AsyncMock(return_value=client),
    )
    gatt_client = GattLinkClient(ble_device, enabled_capabilities=set())

    await gatt_client.start()

    client.read_gatt_char.assert_not_awaited()
    client.start_notify.assert_not_awaited()
    await gatt_client.stop()


@pytest.mark.asyncio
async def test_push_continues_after_one_notification_subscription_fails(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    services = service_collection_factory(
        {
            BATTERY_LEVEL_CHAR_UUID: ["notify"],
            TEMPERATURE_CHAR_UUID: ["notify"],
        }
    )
    client = client_factory(services)

    async def start_notify(
        characteristic: BleakGATTCharacteristic,
        _callback: object,
    ) -> None:
        if characteristic.uuid == BATTERY_LEVEL_CHAR_UUID:
            raise BleakError("battery notification failed")

    client.start_notify.side_effect = start_notify
    monkeypatch.setattr(
        "gatt_link_ble.client.establish_connection",
        AsyncMock(return_value=client),
    )
    gatt_client = GattLinkClient(ble_device)

    await gatt_client.start()

    assert client.start_notify.await_count == 2
    assert "battery notification failed" in caplog.text
    assert gatt_client.get_diagnostics()["failed_characteristics"] == [
        BATTERY_LEVEL_CHAR_UUID
    ]
    await gatt_client.stop()


def test_unknown_enabled_capability_is_rejected(ble_device: BLEDevice) -> None:
    with pytest.raises(ValueError, match="Unsupported enabled capabilities"):
        GattLinkClient(ble_device, enabled_capabilities={"unknown"})


@pytest.mark.parametrize(
    ("connect_timeout", "expected_timeout"),
    [(2.0, 10.0), (12.5, 12.5)],
)
@pytest.mark.asyncio
async def test_provider_falls_back_to_initial_device_and_timeout_floor(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
    connect_timeout: float,
    expected_timeout: float,
) -> None:
    services = service_collection_factory({BATTERY_LEVEL_CHAR_UUID: ["read"]})
    client = client_factory(services)
    client.read_gatt_char.return_value = bytearray(b"\x40")
    establish = AsyncMock(return_value=client)
    monkeypatch.setattr("gatt_link_ble.client.establish_connection", establish)
    provider = Mock(return_value=None)
    gatt_client = GattLinkClient(
        ble_device,
        ConnectionMode.POLL_AND_DISCONNECT,
        ble_device_provider=provider,
        connect_timeout=connect_timeout,
    )

    state = await gatt_client.poll()

    connection_args = establish.await_args
    assert connection_args is not None
    assert connection_args.args[0] is BleakClientWithServiceCache
    assert connection_args.args[0] is not None
    assert connection_args.args[1] is ble_device
    assert connection_args.kwargs["timeout"] == expected_timeout
    assert provider.call_count == 1
    assert state.sensors.battery == 64
    assert gatt_client.get_diagnostics() == {
        "mode": "poll_and_disconnect",
        "connected": False,
        "connect_attempts": 1,
        "last_error": None,
        "active_services": [BATTERY_SERVICE_UUID],
        "failed_characteristics": [],
        "last_updated": state.last_updated.isoformat(),
    }


@pytest.mark.asyncio
async def test_timeout_is_wrapped_and_recorded_in_diagnostics(
    ble_device: BLEDevice,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "gatt_link_ble.client.establish_connection",
        AsyncMock(side_effect=TimeoutError("connect timed out")),
    )
    gatt_client = GattLinkClient(
        ble_device,
        ConnectionMode.POLL_AND_DISCONNECT,
    )

    with pytest.raises(GattTimeoutError, match="connect timed out"):
        await gatt_client.poll()

    diagnostics = gatt_client.get_diagnostics()
    assert diagnostics["connect_attempts"] == 1
    assert diagnostics["last_error"] == "connect timed out"
    assert diagnostics["connected"] is False


@pytest.mark.asyncio
async def test_device_provider_selects_latest_device_on_connection(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = service_collection_factory({BATTERY_LEVEL_CHAR_UUID: ["read"]})
    client = client_factory(services)
    client.read_gatt_char.return_value = bytearray(b"\x40")
    establish = AsyncMock(return_value=client)
    monkeypatch.setattr("gatt_link_ble.client.establish_connection", establish)
    replacement_device = BLEDevice("11:22:33:44:55:66", "Proxy Device", {})
    provider = Mock(return_value=replacement_device)
    gatt_client = GattLinkClient(
        ble_device,
        ConnectionMode.POLL_AND_DISCONNECT,
        ble_device_provider=provider,
    )

    state = await gatt_client.poll()

    assert establish.await_args is not None
    assert establish.await_args.args[1] is replacement_device
    assert state.address == replacement_device.address
    assert state.name == replacement_device.name


@pytest.mark.asyncio
async def test_poll_disconnects_even_when_payload_parsing_fails(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = service_collection_factory({TEMPERATURE_CHAR_UUID: ["read"]})
    client = client_factory(services)
    establish = AsyncMock(return_value=client)
    monkeypatch.setattr("gatt_link_ble.client.establish_connection", establish)
    gatt_client = GattLinkClient(ble_device, ConnectionMode.POLL_AND_DISCONNECT)

    with pytest.raises(GattParseError):
        await gatt_client.poll()

    client.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_push_starts_notifications_and_updates_state(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = service_collection_factory({BATTERY_LEVEL_CHAR_UUID: ["read", "notify"]})
    client = client_factory(services)
    client.read_gatt_char.return_value = bytearray(b"\x32")
    establish = AsyncMock(return_value=client)
    monkeypatch.setattr("gatt_link_ble.client.establish_connection", establish)
    state_callback = Mock()
    gatt_client = GattLinkClient(
        ble_device,
        state_callback=state_callback,
    )

    await gatt_client.start()

    characteristic = services.get_characteristic(BATTERY_LEVEL_CHAR_UUID)
    assert characteristic is not None
    client.start_notify.assert_awaited_once()
    assert gatt_client.state.sensors.battery == 50
    notify_callback = client.start_notify.await_args.args[1]
    await notify_callback(characteristic, bytearray(b"\x5a"))
    assert gatt_client.state.sensors.battery == 90
    assert state_callback.call_args.args[0] == gatt_client.state

    await gatt_client.stop()
    client.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_state_callback_error_is_logged_without_interrupting_updates(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    services = service_collection_factory({BATTERY_LEVEL_CHAR_UUID: ["read", "notify"]})
    client = client_factory(services)
    client.read_gatt_char.return_value = bytearray(b"\x32")
    establish = AsyncMock(return_value=client)
    monkeypatch.setattr("gatt_link_ble.client.establish_connection", establish)
    state_callback = Mock(side_effect=RuntimeError("callback failed"))
    gatt_client = GattLinkClient(
        ble_device,
        state_callback=state_callback,
    )

    await gatt_client.start()

    characteristic = services.get_characteristic(BATTERY_LEVEL_CHAR_UUID)
    assert characteristic is not None
    notify_callback = client.start_notify.await_args.args[1]
    await notify_callback(characteristic, bytearray(b"\x5a"))

    assert gatt_client.state.sensors.battery == 90
    assert "State callback raised an exception" in caplog.text
    await gatt_client.stop()


@pytest.mark.asyncio
async def test_malformed_notification_is_logged_without_changing_state(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    services = service_collection_factory({BATTERY_LEVEL_CHAR_UUID: ["read", "notify"]})
    client = client_factory(services)
    client.read_gatt_char.return_value = bytearray(b"\x32")
    establish = AsyncMock(return_value=client)
    monkeypatch.setattr("gatt_link_ble.client.establish_connection", establish)
    gatt_client = GattLinkClient(ble_device)
    await gatt_client.start()

    characteristic = services.get_characteristic(BATTERY_LEVEL_CHAR_UUID)
    assert characteristic is not None
    notify_callback = client.start_notify.await_args.args[1]
    await notify_callback(characteristic, bytearray())

    assert gatt_client.state.sensors.battery == 50
    assert "Unable to parse characteristic" in caplog.text
    await notify_callback(characteristic, bytearray(b"\x5a"))
    assert gatt_client.state.sensors.battery == 90
    await gatt_client.stop()


@pytest.mark.asyncio
async def test_disconnect_notifies_and_reconnects_with_backoff(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    services = service_collection_factory({TEMPERATURE_CHAR_UUID: ["read", "notify"]})
    first_client = client_factory(services)
    second_client = client_factory(services)
    first_client.read_gatt_char.return_value = bytearray(struct.pack("<h", 2000))
    second_client.read_gatt_char.return_value = bytearray(struct.pack("<h", 2100))
    establish = AsyncMock(
        side_effect=[
            first_client,
            BleakError("ESP_GATT_CONN_CONN_CANCEL"),
            second_client,
        ]
    )
    monkeypatch.setattr("gatt_link_ble.client.establish_connection", establish)
    sleep = AsyncMock()
    monkeypatch.setattr("gatt_link_ble.client.asyncio.sleep", sleep)
    disconnect_callback = Mock(side_effect=RuntimeError("callback failed"))
    replacement_device = BLEDevice("11:22:33:44:55:66", "Proxy Device", {})
    provider = Mock(side_effect=[ble_device, replacement_device, replacement_device])
    gatt_client = GattLinkClient(
        ble_device,
        disconnect_callback=disconnect_callback,
        ble_device_provider=provider,
    )
    await gatt_client.start()

    connection_callback = establish.await_args_list[0].kwargs["disconnected_callback"]
    assert all(
        call.args[0] is BleakClientWithServiceCache
        for call in establish.await_args_list
    )
    connection_callback(first_client)
    reconnect_task = gatt_client._reconnect_task
    assert reconnect_task is not None
    await reconnect_task

    assert disconnect_callback.call_count == 1
    assert "Disconnect callback raised an exception" in caplog.text
    assert [call.args[0] for call in sleep.await_args_list] == [2, 4]
    assert establish.await_count == 3
    assert gatt_client.state.sensors.temperature == 21.0
    assert gatt_client.state.address == replacement_device.address
    assert provider.call_count == 3
    await gatt_client.stop()


@pytest.mark.asyncio
async def test_mode_specific_methods_reject_wrong_mode(ble_device: BLEDevice) -> None:
    push_client = GattLinkClient(ble_device)
    poll_client = GattLinkClient(ble_device, ConnectionMode.POLL_AND_DISCONNECT)

    with pytest.raises(ValueError, match="POLL_AND_DISCONNECT"):
        await push_client.poll()
    with pytest.raises(ValueError, match="PUSH"):
        await poll_client.start()


@pytest.mark.asyncio
async def test_start_is_idempotent_and_stop_cancels_pending_reconnect(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = service_collection_factory({BATTERY_LEVEL_CHAR_UUID: ["read", "notify"]})
    client = client_factory(services)
    client.read_gatt_char.return_value = bytearray(b"\x32")
    establish = AsyncMock(return_value=client)
    monkeypatch.setattr("gatt_link_ble.client.establish_connection", establish)
    entered_sleep = asyncio.Event()

    async def hold_reconnect(_delay: int) -> None:
        entered_sleep.set()
        await asyncio.Future()

    monkeypatch.setattr(
        "gatt_link_ble.client.asyncio.sleep",
        AsyncMock(side_effect=hold_reconnect),
    )
    gatt_client = GattLinkClient(ble_device)
    await gatt_client.start()
    await gatt_client.start()

    connection_args = establish.await_args
    assert connection_args is not None
    connection_callback = connection_args.kwargs["disconnected_callback"]
    connection_callback(client)
    await entered_sleep.wait()
    reconnect_task = gatt_client._reconnect_task
    assert reconnect_task is not None
    await gatt_client.stop()

    assert reconnect_task.cancelled()
    assert establish.await_count == 1


@pytest.mark.asyncio
async def test_start_cleans_up_connection_when_setup_fails(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = service_collection_factory({BATTERY_LEVEL_CHAR_UUID: ["read", "notify"]})
    client = client_factory(services)
    client.start_notify.side_effect = BleakError("notify failed")
    client.read_gatt_char.side_effect = BleakError("read failed")
    establish = AsyncMock(return_value=client)
    monkeypatch.setattr("gatt_link_ble.client.establish_connection", establish)
    gatt_client = GattLinkClient(ble_device)

    with pytest.raises(GattConnectionError, match="any available"):
        await gatt_client.start()

    assert not gatt_client._running
    client.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_push_subscribes_to_indications_and_skips_unreadable_characteristics(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = service_collection_factory({TEMPERATURE_CHAR_UUID: ["indicate"]})
    client = client_factory(services)
    establish = AsyncMock(return_value=client)
    monkeypatch.setattr("gatt_link_ble.client.establish_connection", establish)
    gatt_client = GattLinkClient(ble_device)

    await gatt_client.start()

    client.start_notify.assert_awaited_once()
    client.read_gatt_char.assert_not_awaited()
    assert gatt_client.state.supported_features == frozenset({TEMPERATURE_CHAR_UUID})
    await gatt_client.stop()


@pytest.mark.asyncio
async def test_thingy_poll_updates_each_sensor_field(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = service_collection_factory(
        {
            THINGY_TEMPERATURE_CHAR_UUID: ["read"],
            THINGY_PRESSURE_CHAR_UUID: ["read"],
            THINGY_HUMIDITY_CHAR_UUID: ["read"],
            THINGY_GAS_CHAR_UUID: ["read"],
            THINGY_COLOR_CHAR_UUID: ["read"],
        }
    )
    client = client_factory(services)
    payloads = {
        THINGY_TEMPERATURE_CHAR_UUID: bytearray(struct.pack("<bB", -13, 55)),
        THINGY_PRESSURE_CHAR_UUID: bytearray(struct.pack("<iB", 1013, 25)),
        THINGY_HUMIDITY_CHAR_UUID: bytearray(b"\x46"),
        THINGY_GAS_CHAR_UUID: bytearray(struct.pack("<HH", 500, 60)),
        THINGY_COLOR_CHAR_UUID: bytearray(struct.pack("<HHHH", 1, 2, 3, 400)),
    }

    async def read_characteristic(
        characteristic: BleakGATTCharacteristic,
    ) -> bytearray:
        return payloads[characteristic.uuid]

    client.read_gatt_char.side_effect = read_characteristic
    establish = AsyncMock(return_value=client)
    monkeypatch.setattr("gatt_link_ble.client.establish_connection", establish)
    gatt_client = GattLinkClient(ble_device, ConnectionMode.POLL_AND_DISCONNECT)

    state = await gatt_client.poll()

    assert state.sensors.temperature == -12.45
    assert state.sensors.pressure == 1013.25
    assert state.sensors.humidity == 70.0
    assert state.sensors.eco2 == 500
    assert state.sensors.tvoc == 60
    assert state.sensors.illuminance == 400


@pytest.mark.asyncio
async def test_reconnect_backoff_caps_at_sixty_seconds(
    ble_device: BLEDevice,
    client_factory: ClientFactory,
    service_collection_factory: ServiceCollectionFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    services = service_collection_factory({TEMPERATURE_CHAR_UUID: ["read", "notify"]})
    client = client_factory(services)
    client.read_gatt_char.return_value = bytearray(struct.pack("<h", 2000))
    establish = AsyncMock(
        side_effect=[
            client,
            *(BleakError("offline") for _ in range(6)),
        ]
    )
    monkeypatch.setattr("gatt_link_ble.client.establish_connection", establish)
    delays: list[int] = []
    gatt_client = GattLinkClient(ble_device)

    async def record_delay(delay: int) -> None:
        delays.append(delay)
        if len(delays) == 7:
            gatt_client._running = False

    monkeypatch.setattr(
        "gatt_link_ble.client.asyncio.sleep",
        AsyncMock(side_effect=record_delay),
    )
    await gatt_client.start()
    connection_args = establish.await_args
    assert connection_args is not None
    connection_callback = connection_args.kwargs["disconnected_callback"]
    connection_callback(client)
    reconnect_task = gatt_client._reconnect_task
    assert reconnect_task is not None
    await reconnect_task

    assert delays == [2, 4, 8, 16, 32, 60, 60]
