import struct

import pytest

from gatt_link_ble.const import (
    THINGY_GAS_CHAR_UUID,
    THINGY_HUMIDITY_CHAR_UUID,
    THINGY_PRESSURE_CHAR_UUID,
    THINGY_TEMPERATURE_CHAR_UUID,
)
from gatt_link_ble.exceptions import GattParseError
from gatt_link_ble.parsers import ThingyEnvironmentParser


def test_thingy_parses_negative_temperature() -> None:
    parsed = ThingyEnvironmentParser().parse_characteristic(
        THINGY_TEMPERATURE_CHAR_UUID,
        bytearray(struct.pack("<bB", -13, 55)),
    )

    assert parsed == {"temperature": -12.45}


def test_thingy_parses_pressure_and_humidity() -> None:
    parser = ThingyEnvironmentParser()
    pressure = parser.parse_characteristic(
        THINGY_PRESSURE_CHAR_UUID,
        bytearray(struct.pack("<iB", 1013, 25)),
    )
    humidity = parser.parse_characteristic(
        THINGY_HUMIDITY_CHAR_UUID,
        bytearray(b"\xff"),
    )

    assert pressure == {"pressure": 1013.25}
    assert humidity == {"humidity": 255.0}


def test_thingy_gas_values_are_unsigned() -> None:
    parsed = ThingyEnvironmentParser().parse_characteristic(
        THINGY_GAS_CHAR_UUID,
        bytearray(struct.pack("<HH", 0xFFA0, 0x80FF)),
    )

    assert parsed == {"eco2": 0xFFA0, "tvoc": 0x80FF}


@pytest.mark.parametrize(
    "char_uuid",
    [
        THINGY_TEMPERATURE_CHAR_UUID,
        THINGY_PRESSURE_CHAR_UUID,
        THINGY_HUMIDITY_CHAR_UUID,
        THINGY_GAS_CHAR_UUID,
    ],
)
def test_thingy_rejects_truncated_payload(char_uuid: str) -> None:
    with pytest.raises(GattParseError, match="Invalid payload"):
        ThingyEnvironmentParser().parse_characteristic(char_uuid, bytearray())


def test_thingy_rejects_unknown_characteristic() -> None:
    with pytest.raises(GattParseError, match="Unsupported Thingy"):
        ThingyEnvironmentParser().parse_characteristic(
            "ef680205-9b35-4933-9b10-52ffa9740042",
            bytearray(),
        )
