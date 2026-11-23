from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from bleak.backends.device import BLEDevice

from gatt_link_ble import GattLinkClient
from gatt_link_ble.exceptions import GattConnectionError


@pytest.mark.asyncio
async def test_device_provider_error_is_wrapped_as_connection_error(
    ble_device: BLEDevice,
) -> None:
    provider = Mock(side_effect=RuntimeError("temporary adapter failure"))
    gatt_client = GattLinkClient(ble_device, ble_device_provider=provider)

    with pytest.raises(GattConnectionError, match="temporary adapter failure"):
        await gatt_client._establish_connection()

    diagnostics = gatt_client.get_diagnostics()
    assert diagnostics["connect_attempts"] == 1
    assert diagnostics["last_error"] == "temporary adapter failure"


@pytest.mark.asyncio
async def test_reconnect_continues_when_failed_client_cleanup_raises(
    ble_device: BLEDevice,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    first_client = MagicMock()
    first_client.disconnect = AsyncMock(side_effect=RuntimeError("cleanup failed"))
    second_client = MagicMock()

    gatt_client = GattLinkClient(ble_device)
    gatt_client._running = True
    monkeypatch.setattr(
        "gatt_link_ble.client.asyncio.sleep",
        AsyncMock(),
    )
    monkeypatch.setattr(
        gatt_client,
        "_establish_connection",
        AsyncMock(side_effect=[first_client, second_client]),
    )
    monkeypatch.setattr(gatt_client, "_initialize", AsyncMock())
    monkeypatch.setattr(gatt_client, "_start_notifications", AsyncMock())
    monkeypatch.setattr(gatt_client, "_read_sensor_values", AsyncMock())
    raise_on_first_attempt = Mock(
        side_effect=[GattConnectionError("initialization failed"), None]
    )
    monkeypatch.setattr(
        gatt_client,
        "_raise_if_all_characteristics_failed",
        raise_on_first_attempt,
    )

    await gatt_client._reconnect()

    assert raise_on_first_attempt.call_count == 2
    first_client.disconnect.assert_awaited_once()
    assert "Error cleaning up failed reconnect client" in caplog.text
    assert gatt_client._client is second_client
