import pytest

from gatt_link_ble.const import BATTERY_LEVEL_CHAR_UUID
from gatt_link_ble.exceptions import GattParseError
from gatt_link_ble.parsers import BatteryParser


@pytest.mark.parametrize(("payload", "expected"), [(b"\x00", 0), (b"\x64", 100)])
def test_battery_level_boundaries(payload: bytes, expected: int) -> None:
    parsed = BatteryParser().parse_characteristic(
        BATTERY_LEVEL_CHAR_UUID,
        bytearray(payload),
    )

    assert parsed == {"battery": expected}


@pytest.mark.parametrize("payload", [bytearray(), bytearray(b"\x01\x02")])
def test_battery_rejects_malformed_payload(payload: bytearray) -> None:
    with pytest.raises(GattParseError, match="expected 1 bytes"):
        BatteryParser().parse_characteristic(BATTERY_LEVEL_CHAR_UUID, payload)


def test_battery_rejects_out_of_range_value() -> None:
    with pytest.raises(GattParseError, match="outside 0-100"):
        BatteryParser().parse_characteristic(
            BATTERY_LEVEL_CHAR_UUID,
            bytearray(b"\xa0"),
        )


def test_battery_rejects_unknown_characteristic() -> None:
    with pytest.raises(GattParseError, match="Unsupported battery"):
        BatteryParser().parse_characteristic("2a1a", bytearray(b"\x01"))
