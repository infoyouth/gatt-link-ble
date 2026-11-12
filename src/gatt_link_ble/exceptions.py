"""Library exception hierarchy."""


class GattLinkError(Exception):
    """Base exception for gatt-link-ble."""


class GattConnectionError(GattLinkError):
    """Raised when a BLE connection cannot be established or maintained."""


class GattParseError(GattLinkError):
    """Raised when a GATT characteristic payload cannot be parsed."""
