# gatt-link-ble

An asynchronous, framework-independent Python library for discovering BLE GATT
services, decoding sensor values, and receiving device-state updates.

The package owns BLE transport and parsing. It has no Home Assistant, MQTT, or
UI-framework dependencies.

## Requirements and installation

- Python 3.12 or 3.13
- BLE adapter and a device advertising supported GATT services

Install from PyPI:

```shell
python -m pip install gatt-link-ble
```

## Poll once

```python
import asyncio

from bleak import BleakScanner

from gatt_link_ble import ConnectionMode, GattLinkClient


async def main() -> None:
    address = "AA:BB:CC:DD:EE:FF"
    device = await BleakScanner.find_device_by_address(address, timeout=10)
    if device is None:
        raise RuntimeError(f"BLE device not found: {address}")

    client = GattLinkClient(device, mode=ConnectionMode.POLL_AND_DISCONNECT)
    state = await client.poll()
    print(state)


asyncio.run(main())
```

## Receive push updates

```python
import asyncio

from bleak import BleakScanner

from gatt_link_ble import GattLinkClient


async def main() -> None:
    address = "AA:BB:CC:DD:EE:FF"
    device = await BleakScanner.find_device_by_address(address, timeout=10)
    if device is None:
        raise RuntimeError(f"BLE device not found: {address}")

    client = GattLinkClient(device, state_callback=print)
    await client.start()
    try:
        await asyncio.Event().wait()
    finally:
        await client.stop()


asyncio.run(main())
```

`PUSH` keeps the connection open, sends an initial state after connecting, and
reconnects after unexpected disconnects. `POLL_AND_DISCONNECT` reads available
characteristics once and disconnects before returning.

## Supported profiles

| Profile | Service UUID | Characteristics |
| --- | --- | --- |
| Battery Service | `0x180F` | Battery Level `0x2A19` |
| Heart Rate Service | `0x180D` | Heart Rate Measurement `0x2A37` |
| Device Information | `0x180A` | Manufacturer `0x2A29`, Model `0x2A24`, Firmware `0x2A26`, Hardware `0x2A27` |
| Environmental Sensing | `0x181A` | Temperature `0x2A6E`, Humidity `0x2A6F`, Pressure `0x2A6D` |
| Nordic Thingy Environment | `ef680200-9b35-4933-9b10-52ffa9740042` | Temperature, pressure, humidity, eCO2, TVOC, color/illuminance |

Parsed values are available through the immutable `GattDeviceState`,
`DeviceMetadata`, and `GattSensorData` models.

## Public API and selective capabilities

The stable public API consists of `GattLinkClient`, `ConnectionMode`,
`GattDeviceState`, `GattSensorData`, `DeviceMetadata`, `GattLinkError`,
`GattConnectionError`, `GattTimeoutError`, and `GattParseError`.

By default, the client enables all supported sensor characteristics. Pass
`enabled_capabilities` to limit sensor reads and notifications to the fields
your application uses:

```python
client = GattLinkClient(
    device,
    enabled_capabilities={"temperature", "humidity", "battery"},
)
```

Supported capability names are `temperature`, `humidity`, `pressure`, `eco2`,
`tvoc`, `battery`, `illuminance`, and `heart_rate`. `None` enables all
capabilities; an empty set disables sensor I/O. Device Information is read
independently when available.

For devices whose `BLEDevice` changes during proxy handoffs, pass a provider.
Returning `None` falls back to the original device. `connect_timeout` is
enforced with a minimum of 10 seconds:

```python
client = GattLinkClient(
    device,
    ble_device_provider=get_latest_ble_device,
    connect_timeout=10.0,
)
```

Each connection attempt creates a fresh `BleakClientWithServiceCache`.
`get_diagnostics()` returns a snapshot containing the connection mode and
status, number of calls to `establish_connection`, latest error, active
services, failed characteristic UUIDs, and the state's ISO-8601 `last_updated`
timestamp:

```python
print(client.get_diagnostics())
```

## Inspect a device

The hardware diagnostic script lists nearby devices and, when passed an
address, dumps raw bytes from readable characteristics:

```shell
uv run python scripts/live_scan.py
uv run python scripts/live_scan.py AA:BB:CC:DD:EE:FF --timeout 10
```

The output may include MAC addresses or other personal identifiers; redact
them before sharing it publicly.

## Development

```shell
uv sync --locked --all-groups
uv run ruff check .
uv run mypy src tests
uv run pytest
uv build
```

Tests use mocked BLE clients and GATT services; no hardware is needed.
`ARCHITECTURE.md` is a local implementation guide and is intentionally not
included in the public repository.
