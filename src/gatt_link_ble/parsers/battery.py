"""Parser for the Bluetooth SIG Battery Service."""

from typing import ClassVar

from ..const import BATTERY_LEVEL_CHAR_UUID, BATTERY_SERVICE_UUID
from ..exceptions import GattParseError
from ..registry import register_gatt_parser
from .base import normalize_uuid, unpack_struct


@register_gatt_parser
class BatteryParser:
    """Parse the Battery Level characteristic."""

    service_uuid: ClassVar[str] = BATTERY_SERVICE_UUID
    characteristic_uuids: ClassVar[tuple[str, ...]] = (BATTERY_LEVEL_CHAR_UUID,)

    def parse_characteristic(
        self,
        char_uuid: str,
        data: bytearray,
    ) -> dict[str, object]:
        if normalize_uuid(char_uuid) != BATTERY_LEVEL_CHAR_UUID:
            raise GattParseError(f"Unsupported battery characteristic: {char_uuid}")

        (battery,) = unpack_struct("<B", data, char_uuid)
        if battery > 100:
            raise GattParseError(f"Battery level is outside 0-100%: {battery}")
        return {"battery": battery}
