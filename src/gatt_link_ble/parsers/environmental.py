"""Parser for the Bluetooth SIG Environmental Sensing Service."""

from typing import ClassVar

from ..const import (
    ENVIRONMENTAL_SENSING_SERVICE_UUID,
    HUMIDITY_CHAR_UUID,
    PRESSURE_CHAR_UUID,
    TEMPERATURE_CHAR_UUID,
)
from ..exceptions import GattParseError
from ..registry import register_gatt_parser
from .base import normalize_uuid, unpack_struct


@register_gatt_parser
class EnvironmentalParser:
    """Parse temperature, humidity, and pressure values."""

    service_uuid: ClassVar[str] = ENVIRONMENTAL_SENSING_SERVICE_UUID
    characteristic_uuids: ClassVar[tuple[str, ...]] = (
        TEMPERATURE_CHAR_UUID,
        HUMIDITY_CHAR_UUID,
        PRESSURE_CHAR_UUID,
    )

    def parse_characteristic(
        self,
        char_uuid: str,
        data: bytearray,
    ) -> dict[str, object]:
        normalized_uuid = normalize_uuid(char_uuid)
        if normalized_uuid == TEMPERATURE_CHAR_UUID:
            (value,) = unpack_struct("<h", data, char_uuid)
            return {"temperature": value / 100.0}
        if normalized_uuid == HUMIDITY_CHAR_UUID:
            (value,) = unpack_struct("<H", data, char_uuid)
            return {"humidity": value / 100.0}
        if normalized_uuid == PRESSURE_CHAR_UUID:
            (value,) = unpack_struct("<I", data, char_uuid)
            return {"pressure": value / 1000.0}
        raise GattParseError(f"Unsupported environmental characteristic: {char_uuid}")
