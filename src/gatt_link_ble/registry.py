"""Registry for self-registering GATT parsers."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from bleak.uuids import normalize_uuid_str

if TYPE_CHECKING:
    from .parsers.base import BaseGattParser

GATT_PARSER_REGISTRY: dict[str, type[BaseGattParser]] = {}


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
