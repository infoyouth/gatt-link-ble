import json
from pathlib import Path

import pytest

from gatt_link_ble.const import (
    BATTERY_LEVEL_CHAR_UUID,
    THINGY_COLOR_CHAR_UUID,
    THINGY_GAS_CHAR_UUID,
    THINGY_HUMIDITY_CHAR_UUID,
    THINGY_PRESSURE_CHAR_UUID,
    THINGY_TEMPERATURE_CHAR_UUID,
)
from gatt_link_ble.parsers import BatteryParser, ThingyEnvironmentParser

_FIXTURE_PATH = Path(__file__).parent.parent / "fixtures" / "thingy52_payloads.json"


def _load_payloads() -> dict[str, str]:
    fixture: object = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(fixture, dict)
    payloads = fixture.get("payloads")
    assert isinstance(payloads, dict)

    decoded_payloads: dict[str, str] = {}
    for char_uuid, payload in payloads.items():
        assert isinstance(char_uuid, str)
        assert isinstance(payload, str)
        decoded_payloads[char_uuid] = payload
    return decoded_payloads


@pytest.mark.parametrize(
    ("char_uuid", "expected"),
    [
        (THINGY_TEMPERATURE_CHAR_UUID, {"temperature": 20.03}),
        (THINGY_PRESSURE_CHAR_UUID, {"pressure": 1004.22}),
        (THINGY_HUMIDITY_CHAR_UUID, {"humidity": 60.0}),
        (THINGY_GAS_CHAR_UUID, {"eco2": 0, "tvoc": 0}),
        (THINGY_COLOR_CHAR_UUID, {"illuminance": 221}),
    ],
)
def test_recorded_thingy_payloads_parse(
    char_uuid: str,
    expected: dict[str, float | int],
) -> None:
    payload = bytes.fromhex(_load_payloads()[char_uuid])

    assert (
        ThingyEnvironmentParser().parse_characteristic(
            char_uuid,
            bytearray(payload),
        )
        == expected
    )


def test_recorded_battery_payload_parses() -> None:
    payload = bytes.fromhex(_load_payloads()[BATTERY_LEVEL_CHAR_UUID])

    assert BatteryParser().parse_characteristic(
        BATTERY_LEVEL_CHAR_UUID,
        bytearray(payload),
    ) == {"battery": 64}
