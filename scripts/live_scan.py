"""Discover nearby BLE devices and dump readable GATT characteristic values."""

import argparse
import asyncio
import logging

from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    establish_connection,
)

_LOGGER = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "address",
        nargs="?",
        help="BLE address to inspect; omit to list discovered devices",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=5.0,
        help="scan duration in seconds (default: 5)",
    )
    return parser.parse_args()


async def _inspect_device(device: BLEDevice) -> None:
    client = await establish_connection(
        BleakClientWithServiceCache,
        device,
        device.name or device.address,
        max_attempts=3,
    )
    try:
        for service in client.services:
            print(f"\nService {service.uuid}")
            for characteristic in service.characteristics:
                properties = ", ".join(characteristic.properties)
                print(f"  Characteristic {characteristic.uuid} [{properties}]")
                if "read" not in characteristic.properties:
                    continue
                try:
                    value = await client.read_gatt_char(characteristic)
                except BleakError as err:
                    _LOGGER.warning(
                        "Could not read characteristic %s: %s",
                        characteristic.uuid,
                        err,
                    )
                    continue
                print(f"    Raw: {value.hex(' ')}")
    finally:
        await client.disconnect()


async def _run(args: argparse.Namespace) -> None:
    try:
        devices = await BleakScanner.discover(timeout=args.timeout)
    except BleakError as err:
        raise SystemExit(f"BLE scan failed: {err}") from err

    for device in devices:
        print(f"{device.address}  {device.name or '(unnamed)'}")

    if args.address is None:
        return

    match = next(
        (
            candidate
            for candidate in devices
            if candidate.address.casefold() == args.address.casefold()
        ),
        None,
    )
    if match is None:
        raise SystemExit(f"No discovered BLE device matches {args.address}")

    try:
        await _inspect_device(match)
    except BleakError as err:
        raise SystemExit(f"Unable to inspect {match.address}: {err}") from err


def main() -> None:
    """Run the BLE scanner CLI."""
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    asyncio.run(_run(_parse_args()))


if __name__ == "__main__":
    main()
