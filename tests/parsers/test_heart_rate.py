import struct

import pytest

from gatt_link_ble.const import HEART_RATE_MEASUREMENT_CHAR_UUID
from gatt_link_ble.exceptions import GattParseError
from gatt_link_ble.parsers import HeartRateParser


def test_heart_rate_parses_uint8_measurement() -> None:
    parsed = HeartRateParser().parse_characteristic(
        HEART_RATE_MEASUREMENT_CHAR_UUID,
        bytearray(struct.pack("<BB", 0x00, 72)),
    )

    assert parsed == {"heart_rate": 72}


def test_heart_rate_parses_uint16_measurement() -> None:
    parsed = HeartRateParser().parse_characteristic(
        HEART_RATE_MEASUREMENT_CHAR_UUID,
        bytearray(struct.pack("<BH", 0x01, 300)),
    )

    assert parsed == {"heart_rate": 300}


def test_heart_rate_skips_optional_energy_and_rr_data() -> None:
    parsed = HeartRateParser().parse_characteristic(
        HEART_RATE_MEASUREMENT_CHAR_UUID,
        bytearray(struct.pack("<BBHHH", 0x18, 72, 120, 1024, 512)),
    )

    assert parsed == {"heart_rate": 72}


@pytest.mark.parametrize(
    "payload",
    [
        bytearray(),
        bytearray(b"\x00"),
        bytearray(b"\x01\x2c"),
        bytearray(b"\x08\x48"),
        bytearray(b"\x10\x48"),
        bytearray(b"\x10\x48\x01"),
        bytearray(b"\x00\x48\x00"),
    ],
)
def test_heart_rate_rejects_malformed_measurements(payload: bytearray) -> None:
    with pytest.raises(GattParseError):
        HeartRateParser().parse_characteristic(
            HEART_RATE_MEASUREMENT_CHAR_UUID,
            payload,
        )


def test_heart_rate_rejects_unknown_characteristic() -> None:
    with pytest.raises(GattParseError, match="Unsupported heart rate"):
        HeartRateParser().parse_characteristic("2a38", bytearray(b"\x00\x48"))
