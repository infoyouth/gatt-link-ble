"""Library exception hierarchy."""


class GattLinkError(Exception):
    """Base exception for gatt-link-ble."""


class GattConnectionError(GattLinkError):
    """Raised when a BLE connection cannot be established or maintained."""


class GattTimeoutError(GattConnectionError):
    """Raised when a BLE operation times out."""


class GattParseError(GattLinkError):
    """Raised when a GATT characteristic payload cannot be parsed."""
