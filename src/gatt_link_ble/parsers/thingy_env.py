"""Parser for the Nordic Thingy environment service."""

from typing import ClassVar

from ..const import (
    THINGY_ENVIRONMENT_SERVICE_UUID,
    THINGY_GAS_CHAR_UUID,
    THINGY_HUMIDITY_CHAR_UUID,
    THINGY_PRESSURE_CHAR_UUID,
    THINGY_TEMPERATURE_CHAR_UUID,
)
from ..exceptions import GattParseError
from ..registry import register_gatt_parser
from .base import normalize_uuid, unpack_struct


@register_gatt_parser
class ThingyEnvironmentParser:
    """Decode Nordic Thingy temperature, pressure, humidity, and gas data."""

    service_uuid: ClassVar[str] = THINGY_ENVIRONMENT_SERVICE_UUID
    characteristic_uuids: ClassVar[tuple[str, ...]] = (
        THINGY_TEMPERATURE_CHAR_UUID,
        THINGY_PRESSURE_CHAR_UUID,
        THINGY_HUMIDITY_CHAR_UUID,
        THINGY_GAS_CHAR_UUID,
    )

    def parse_characteristic(
        self,
        char_uuid: str,
        data: bytearray,
    ) -> dict[str, object]:
        normalized_uuid = normalize_uuid(char_uuid)
        if normalized_uuid == THINGY_TEMPERATURE_CHAR_UUID:
            integer, decimal = unpack_struct("<bB", data, char_uuid)
            return {"temperature": integer + decimal / 100.0}
        if normalized_uuid == THINGY_PRESSURE_CHAR_UUID:
            integer, decimal = unpack_struct("<iB", data, char_uuid)
            return {"pressure": integer + decimal / 100.0}
        if normalized_uuid == THINGY_HUMIDITY_CHAR_UUID:
            (value,) = unpack_struct("<B", data, char_uuid)
            return {"humidity": float(value)}
        if normalized_uuid == THINGY_GAS_CHAR_UUID:
            eco2, tvoc = unpack_struct("<HH", data, char_uuid)
            return {"eco2": eco2, "tvoc": tvoc}
        raise GattParseError(
            f"Unsupported Thingy environment characteristic: {char_uuid}"
        )
