import pytest

from gatt_link_ble.const import (
    FIRMWARE_REVISION_CHAR_UUID,
    HARDWARE_REVISION_CHAR_UUID,
    MANUFACTURER_NAME_CHAR_UUID,
    MODEL_NUMBER_CHAR_UUID,
)
from gatt_link_ble.exceptions import GattParseError
from gatt_link_ble.parsers import DeviceInfoParser


@pytest.mark.parametrize(
    ("char_uuid", "payload", "field", "expected"),
    [
        (MANUFACTURER_NAME_CHAR_UUID, b"N\xc3\xb8rdic\x00", "manufacturer", "Nørdic"),
        (MODEL_NUMBER_CHAR_UUID, b"Thingy:52", "model", "Thingy:52"),
        (FIRMWARE_REVISION_CHAR_UUID, b"1.2.3", "firmware_revision", "1.2.3"),
        (HARDWARE_REVISION_CHAR_UUID, b"rev A", "hardware_revision", "rev A"),
    ],
)
def test_device_information_strings(
    char_uuid: str,
    payload: bytes,
    field: str,
    expected: str,
) -> None:
    assert DeviceInfoParser().parse_characteristic(
        char_uuid,
        bytearray(payload),
    ) == {field: expected}


def test_device_information_rejects_invalid_utf8() -> None:
    with pytest.raises(GattParseError, match="Invalid UTF-8"):
        DeviceInfoParser().parse_characteristic(
            MANUFACTURER_NAME_CHAR_UUID,
            bytearray(b"\xff"),
        )


def test_device_information_rejects_unknown_characteristic() -> None:
    with pytest.raises(GattParseError, match="Unsupported device information"):
        DeviceInfoParser().parse_characteristic("2a28", bytearray(b"value"))
