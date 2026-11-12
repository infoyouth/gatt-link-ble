"""Shared parser protocol and binary decoding helpers."""

import struct
from typing import ClassVar, Protocol

from bleak.uuids import normalize_uuid_str

from ..exceptions import GattParseError


class BaseGattParser(Protocol):
    """Contract implemented by each GATT service parser."""

    service_uuid: ClassVar[str]
    characteristic_uuids: ClassVar[tuple[str, ...]]

    def parse_characteristic(
        self,
        char_uuid: str,
        data: bytearray,
    ) -> dict[str, object]: ...


def normalize_uuid(uuid: str) -> str:
    """Return a canonical Bluetooth UUID."""
    return normalize_uuid_str(uuid)


def unpack_struct(
    format_string: str,
    data: bytearray,
    char_uuid: str,
) -> tuple[int, ...]:
    """Unpack an exact-size payload or raise the library parse error."""
    try:
        return struct.unpack(format_string, data)
    except struct.error as err:
        expected_length = struct.calcsize(format_string)
        raise GattParseError(
            f"Invalid payload for {char_uuid}: expected {expected_length} bytes, "
            f"got {len(data)}"
        ) from err
