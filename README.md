# gatt-link-ble

An asynchronous, framework-independent Python library for discovering BLE GATT
services, decoding sensor values, and receiving device-state updates.

The package owns BLE transport and parsing. It has no Home Assistant, MQTT, or
UI-framework dependencies.

## Requirements and installation

- Python 3.12 or newer
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
| Nordic Thingy Environment | `ef680200-9b35-4933-9b10-52ffa9740042` | Temperature, pressure, humidity, eCO2, TVOC |

Parsed values are available through the immutable `GattDeviceState`,
`DeviceMetadata`, and `GattSensorData` models.

## Inspect a device

The hardware diagnostic script lists nearby devices and, when passed an
address, dumps raw bytes from readable characteristics:

```shell
uv run python scripts/live_scan.py
uv run python scripts/live_scan.py AA:BB:CC:DD:EE:FF --timeout 10
```

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

## Releases

After CI succeeds on `main`, Python Semantic Release uses Conventional Commits
(`feat:` for minor, `fix:` or `perf:` for patch, and `!` for breaking changes)
to update the version, create a GitHub release, and push a tag. Configure the
repository Actions secret `RELEASE_PAT` with a GitHub token that can write to
this repository and whose account is allowed to bypass the `main` branch rules.

The PAT is only for GitHub release operations; it is not a PyPI token. PyPI
publishing uses OIDC Trusted Publishing. Configure the PyPI publisher for this
repository's `publish.yml` workflow before the first upload.
