from typing import ClassVar

import pytest

from gatt_link_ble.const import (
    BATTERY_SERVICE_UUID,
    ENVIRONMENTAL_SENSING_SERVICE_UUID,
    HEART_RATE_SERVICE_UUID,
)
from gatt_link_ble.parsers import (
    BatteryParser,
    DeviceInfoParser,
    EnvironmentalParser,
    HeartRateParser,
    ThingyEnvironmentParser,
)
from gatt_link_ble.registry import (
    GATT_PARSER_REGISTRY,
    get_parsers_for_services,
    register_gatt_parser,
)


def test_built_in_parsers_register_by_service() -> None:
    assert GATT_PARSER_REGISTRY[BATTERY_SERVICE_UUID] is BatteryParser
    assert (
        GATT_PARSER_REGISTRY[ENVIRONMENTAL_SENSING_SERVICE_UUID] is EnvironmentalParser
    )
    assert GATT_PARSER_REGISTRY[HEART_RATE_SERVICE_UUID] is HeartRateParser


def test_registry_matches_normalized_services_and_ignores_unknown() -> None:
    parsers = get_parsers_for_services(["180d", "180f", "181a", "ffff"])

    assert {type(parser) for parser in parsers} == {
        BatteryParser,
        EnvironmentalParser,
        HeartRateParser,
    }


def test_registry_instantiates_device_information_and_thingy_parsers() -> None:
    parsers = get_parsers_for_services(
        [
            DeviceInfoParser.service_uuid,
            ThingyEnvironmentParser.service_uuid,
        ]
    )

    assert {type(parser) for parser in parsers} == {
        DeviceInfoParser,
        ThingyEnvironmentParser,
    }


def test_duplicate_service_registration_is_rejected() -> None:
    with pytest.raises(ValueError, match="already registered"):

        @register_gatt_parser
        class DuplicateBatteryParser:
            service_uuid: ClassVar[str] = BATTERY_SERVICE_UUID
            characteristic_uuids: ClassVar[tuple[str, ...]] = ()

            def parse_characteristic(
                self,
                char_uuid: str,
                data: bytearray,
            ) -> dict[str, object]:
                return {}
