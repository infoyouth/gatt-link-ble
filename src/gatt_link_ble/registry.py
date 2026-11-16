"""Registry for self-registering GATT parsers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from bleak.uuids import normalize_uuid_str

from .const import (
    BATTERY_LEVEL_CHAR_UUID,
    HEART_RATE_MEASUREMENT_CHAR_UUID,
    HUMIDITY_CHAR_UUID,
    PRESSURE_CHAR_UUID,
    TEMPERATURE_CHAR_UUID,
    THINGY_COLOR_CHAR_UUID,
    THINGY_GAS_CHAR_UUID,
    THINGY_HUMIDITY_CHAR_UUID,
    THINGY_PRESSURE_CHAR_UUID,
    THINGY_TEMPERATURE_CHAR_UUID,
)

if TYPE_CHECKING:
    from .parsers.base import BaseGattParser

GATT_PARSER_REGISTRY: dict[str, type[BaseGattParser]] = {}

_CAPABILITIES_BY_CHARACTERISTIC = {
    BATTERY_LEVEL_CHAR_UUID: frozenset({"battery"}),
    HEART_RATE_MEASUREMENT_CHAR_UUID: frozenset({"heart_rate"}),
    TEMPERATURE_CHAR_UUID: frozenset({"temperature"}),
    HUMIDITY_CHAR_UUID: frozenset({"humidity"}),
    PRESSURE_CHAR_UUID: frozenset({"pressure"}),
    THINGY_TEMPERATURE_CHAR_UUID: frozenset({"temperature"}),
    THINGY_PRESSURE_CHAR_UUID: frozenset({"pressure"}),
    THINGY_HUMIDITY_CHAR_UUID: frozenset({"humidity"}),
    THINGY_GAS_CHAR_UUID: frozenset({"eco2", "tvoc"}),
    THINGY_COLOR_CHAR_UUID: frozenset({"illuminance"}),
}


def register_gatt_parser(
    parser_class: type[BaseGattParser],
) -> type[BaseGattParser]:
    """Register a parser class by its normalized service UUID."""
    service_uuid = normalize_uuid_str(parser_class.service_uuid)
    if service_uuid in GATT_PARSER_REGISTRY:
        raise ValueError(f"A parser is already registered for {service_uuid}")

    GATT_PARSER_REGISTRY[service_uuid] = parser_class
    return parser_class


def get_parsers_for_services(
    service_uuids: Iterable[str],
) -> tuple[BaseGattParser, ...]:
    """Instantiate registered parsers matching the supplied service UUIDs."""
    available_services = {normalize_uuid_str(uuid) for uuid in service_uuids}
    return tuple(
        parser_class()
        for service_uuid, parser_class in GATT_PARSER_REGISTRY.items()
        if service_uuid in available_services
    )


def get_characteristics_for_capabilities(
    parser: BaseGattParser,
    enabled_capabilities: frozenset[str] | None,
) -> tuple[str, ...]:
    """Return parser characteristics selected by the enabled sensor fields."""
    if enabled_capabilities is None:
        return parser.characteristic_uuids

    return tuple(
        char_uuid
        for char_uuid in parser.characteristic_uuids
        if _CAPABILITIES_BY_CHARACTERISTIC.get(
            normalize_uuid_str(char_uuid),
            frozenset(),
        )
        & enabled_capabilities
    )
