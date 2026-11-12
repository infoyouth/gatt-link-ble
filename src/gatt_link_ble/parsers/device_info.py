"""Parser for the Bluetooth SIG Device Information Service."""

from typing import ClassVar

from ..const import (
    DEVICE_INFORMATION_SERVICE_UUID,
    FIRMWARE_REVISION_CHAR_UUID,
    HARDWARE_REVISION_CHAR_UUID,
    MANUFACTURER_NAME_CHAR_UUID,
    MODEL_NUMBER_CHAR_UUID,
)
from ..exceptions import GattParseError
from ..registry import register_gatt_parser
from .base import normalize_uuid


@register_gatt_parser
class DeviceInfoParser:
    """Decode Device Information Service string characteristics."""

    service_uuid: ClassVar[str] = DEVICE_INFORMATION_SERVICE_UUID
    characteristic_uuids: ClassVar[tuple[str, ...]] = (
        MANUFACTURER_NAME_CHAR_UUID,
        MODEL_NUMBER_CHAR_UUID,
        FIRMWARE_REVISION_CHAR_UUID,
        HARDWARE_REVISION_CHAR_UUID,
    )
    _field_by_uuid: ClassVar[dict[str, str]] = {
        MANUFACTURER_NAME_CHAR_UUID: "manufacturer",
        MODEL_NUMBER_CHAR_UUID: "model",
        FIRMWARE_REVISION_CHAR_UUID: "firmware_revision",
        HARDWARE_REVISION_CHAR_UUID: "hardware_revision",
    }

    def parse_characteristic(
        self,
        char_uuid: str,
        data: bytearray,
    ) -> dict[str, object]:
        field_name = self._field_by_uuid.get(normalize_uuid(char_uuid))
        if field_name is None:
            raise GattParseError(
                f"Unsupported device information characteristic: {char_uuid}"
            )

        try:
            value = data.decode("utf-8").rstrip("\x00")
        except UnicodeDecodeError as err:
            raise GattParseError(
                f"Invalid UTF-8 in device information characteristic {char_uuid}"
            ) from err
        return {field_name: value}
