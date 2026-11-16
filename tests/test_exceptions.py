from gatt_link_ble import (
    GattConnectionError,
    GattLinkError,
    GattParseError,
    GattTimeoutError,
)


def test_specific_errors_inherit_from_library_error() -> None:
    assert issubclass(GattConnectionError, GattLinkError)
    assert issubclass(GattParseError, GattLinkError)
    assert issubclass(GattTimeoutError, GattConnectionError)
