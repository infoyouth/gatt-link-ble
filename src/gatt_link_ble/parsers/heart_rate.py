"""Parser for the Bluetooth SIG Heart Rate Service."""

from typing import ClassVar

from ..const import HEART_RATE_MEASUREMENT_CHAR_UUID, HEART_RATE_SERVICE_UUID
from ..exceptions import GattParseError
from ..registry import register_gatt_parser
from .base import normalize_uuid, unpack_struct


@register_gatt_parser
class HeartRateParser:
    """Parse Heart Rate Measurement values."""

    service_uuid: ClassVar[str] = HEART_RATE_SERVICE_UUID
    characteristic_uuids: ClassVar[tuple[str, ...]] = (
        HEART_RATE_MEASUREMENT_CHAR_UUID,
    )

    def parse_characteristic(
        self,
        char_uuid: str,
        data: bytearray,
    ) -> dict[str, object]:
        if normalize_uuid(char_uuid) != HEART_RATE_MEASUREMENT_CHAR_UUID:
            raise GattParseError(f"Unsupported heart rate characteristic: {char_uuid}")

        (flags,) = unpack_struct("<B", data[:1], char_uuid)
        offset = 1
        if flags & 0x01:
            (heart_rate,) = unpack_struct("<H", data[offset : offset + 2], char_uuid)
            offset += 2
        else:
            (heart_rate,) = unpack_struct("<B", data[offset : offset + 1], char_uuid)
            offset += 1

        if flags & 0x08:
            unpack_struct("<H", data[offset : offset + 2], char_uuid)
            offset += 2

        if flags & 0x10:
            rr_intervals = data[offset:]
            if not rr_intervals or len(rr_intervals) % 2:
                raise GattParseError(
                    f"Invalid RR interval data for {char_uuid}: "
                    f"expected complete 2-byte values, got {len(rr_intervals)} bytes"
                )
            for index in range(0, len(rr_intervals), 2):
                unpack_struct("<H", rr_intervals[index : index + 2], char_uuid)
        elif offset != len(data):
            raise GattParseError(
                f"Unexpected trailing data for {char_uuid}: "
                f"expected {offset} bytes, got {len(data)}"
            )

        return {"heart_rate": heart_rate}
