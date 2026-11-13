"""Immutable public data models."""

from dataclasses import dataclass, field
from enum import StrEnum


class ConnectionMode(StrEnum):
    """How the client maintains its BLE connection."""

    PUSH = "push"
    POLL_AND_DISCONNECT = "poll_and_disconnect"


@dataclass(frozen=True)
class DeviceMetadata:
    """Device Information Service values."""

    manufacturer: str | None = None
    model: str | None = None
    firmware_revision: str | None = None
    hardware_revision: str | None = None


@dataclass(frozen=True)
class GattSensorData:
    """Values parsed from supported GATT sensor characteristics."""

    temperature: float | None = None
    humidity: float | None = None
    pressure: float | None = None
    eco2: int | None = None
    tvoc: int | None = None
    battery: int | None = None
    illuminance: int | None = None
    heart_rate: int | None = None


@dataclass(frozen=True)
class GattDeviceState:
    """Immutable snapshot of a BLE device and its parsed values."""

    address: str
    name: str | None = None
    metadata: DeviceMetadata = field(default_factory=DeviceMetadata)
    sensors: GattSensorData = field(default_factory=GattSensorData)
    supported_features: frozenset[str] = frozenset()
