import struct

import pytest

from gatt_link_ble.const import (
    HUMIDITY_CHAR_UUID,
    PRESSURE_CHAR_UUID,
    TEMPERATURE_CHAR_UUID,
)
from gatt_link_ble.exceptions import GattParseError
from gatt_link_ble.parsers import EnvironmentalParser


def test_environmental_parses_negative_temperature() -> None:
    parsed = EnvironmentalParser().parse_characteristic(
        TEMPERATURE_CHAR_UUID,
        bytearray(struct.pack("<h", -1245)),
    )

    assert parsed == {"temperature": -12.45}


def test_environmental_preserves_unsigned_high_bytes() -> None:
    parser = EnvironmentalParser()
    humidity = parser.parse_characteristic(
        HUMIDITY_CHAR_UUID,
        bytearray(struct.pack("<H", 0xFFA0)),
    )
    pressure = parser.parse_characteristic(
        PRESSURE_CHAR_UUID,
        bytearray(struct.pack("<I", 0xFFFFFFFF)),
    )

    assert humidity == {"humidity": 654.4}
    assert pressure == {"pressure": 0xFFFFFFFF / 1000.0}


@pytest.mark.parametrize(
    "char_uuid",
    [TEMPERATURE_CHAR_UUID, HUMIDITY_CHAR_UUID, PRESSURE_CHAR_UUID],
)
def test_environmental_rejects_truncated_payload(char_uuid: str) -> None:
    with pytest.raises(GattParseError, match="Invalid payload"):
        EnvironmentalParser().parse_characteristic(char_uuid, bytearray())


def test_environmental_rejects_unknown_characteristic() -> None:
    with pytest.raises(GattParseError, match="Unsupported environmental"):
        EnvironmentalParser().parse_characteristic("2a1a", bytearray(b"\x00"))
