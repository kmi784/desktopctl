import dbus

from desktopctl.misc import translate_dbus_errors

from ._bluez import (
    ADAPTER_PATH,
    BLUEZ_ADAPTER_INTERFACE,
    BLUEZ_BATTERY_INTERFACE,
    BLUEZ_DEVICE_INTERFACE,
    BLUEZ_ROOT_PATH,
    BLUEZ_SERVICE,
    DBUS_OBJECT_MANAGER_INTERFACE,
    PAIRING_TIMEOUT,
    BluetoothDevice,
    BluetoothError,
    _BlueZGateway,
    _BlueZPairingSession,
)
from .bluez_agent import (
    BLUEZ_AGENT_CAPABILITY,
    BLUEZ_AGENT_MANAGER_INTERFACE,
    BLUEZ_AGENT_MANAGER_PATH,
    BLUEZ_AGENT_PATH,
    BlueZAgent,
)

__all__ = [
    "ADAPTER_PATH",
    "BLUEZ_ADAPTER_INTERFACE",
    "BLUEZ_AGENT_CAPABILITY",
    "BLUEZ_AGENT_MANAGER_INTERFACE",
    "BLUEZ_AGENT_MANAGER_PATH",
    "BLUEZ_AGENT_PATH",
    "BLUEZ_BATTERY_INTERFACE",
    "BLUEZ_DEVICE_INTERFACE",
    "BLUEZ_ROOT_PATH",
    "BLUEZ_SERVICE",
    "DBUS_OBJECT_MANAGER_INTERFACE",
    "PAIRING_TIMEOUT",
    "BlueZAgent",
    "BluetoothDevice",
    "BluetoothError",
    "bluetooth_is_enabled",
    "connect_bluetooth_device",
    "disconnect_bluetooth_device",
    "enable_bluetooth",
    "forget_bluetooth_device",
    "list_connected_bluetooth_devices",
    "list_paired_bluetooth_devices",
    "list_visible_bluetooth_devices",
    "pair_bluetooth_device",
    "scan_bluetooth_devices",
]


def _gateway() -> _BlueZGateway:
    """Return a BlueZ gateway connected to the system bus."""
    return _BlueZGateway(dbus.SystemBus())


@translate_dbus_errors(BluetoothError)
def bluetooth_is_enabled() -> bool:
    """Return whether Bluetooth is enabled.

    Returns
    -------
    `bool`
        `True` if Bluetooth is enabled; otherwise, `False`.
    """
    return _gateway().bluetooth_is_enabled()


@translate_dbus_errors(BluetoothError)
def list_visible_bluetooth_devices() -> list[BluetoothDevice]:
    """List all visible Bluetooth devices.

    Returns
    -------
    `list[BluetoothDevice]`
        Visible Bluetooth devices reported by BlueZ.
    """
    return _gateway().list_visible_bluetooth_devices()


def list_connected_bluetooth_devices() -> list[BluetoothDevice]:
    """List all connected Bluetooth devices.

    Returns
    -------
    `list[BluetoothDevice]`
        Connected Bluetooth devices reported by BlueZ.
    """
    return [device for device in list_visible_bluetooth_devices() if device.connected]


def list_paired_bluetooth_devices() -> list[BluetoothDevice]:
    """List all paired Bluetooth devices.

    Returns
    -------
    `list[BluetoothDevice]`
        Paired Bluetooth devices reported by BlueZ.
    """
    return [device for device in list_visible_bluetooth_devices() if device.paired]


@translate_dbus_errors(BluetoothError)
def enable_bluetooth(enable: bool) -> None:
    """Enable or disable Bluetooth.

    Parameters
    ----------
    `enable` : `bool`
        Whether to enable (`True`) or disable (`False`) Bluetooth.
    """
    _gateway().enable_bluetooth(enable)


@translate_dbus_errors(BluetoothError)
def scan_bluetooth_devices(duration: int = 10) -> None:
    """Scan for nearby Bluetooth devices.

    Parameters
    ----------
    `duration` : `int`, optional
        Scan duration in seconds.
    """
    _gateway().scan_bluetooth_devices(duration)


@translate_dbus_errors(BluetoothError)
def pair_bluetooth_device(address: str) -> None:
    """Pair and trust a Bluetooth device using a temporary BlueZ agent.

    Parameters
    ----------
    `address` : `str`
        Address of a Bluetooth device discovered by BlueZ.
    """
    with _BlueZPairingSession(address) as session:
        session.pair()


@translate_dbus_errors(BluetoothError)
def connect_bluetooth_device(address: str) -> None:
    """Connect a paired Bluetooth device.

    Parameters
    ----------
    `address` : `str`
        Address of a Bluetooth device known to BlueZ.
    """
    _gateway().connect_bluetooth_device(address)


@translate_dbus_errors(BluetoothError)
def disconnect_bluetooth_device(address: str) -> None:
    """Disconnect a Bluetooth device.

    Parameters
    ----------
    `address` : `str`
        Address of a Bluetooth device known to BlueZ.
    """
    _gateway().disconnect_bluetooth_device(address)


@translate_dbus_errors(BluetoothError)
def forget_bluetooth_device(address: str) -> None:
    """Forget a paired Bluetooth device.

    Parameters
    ----------
    `address` : `str`
        Address of a Bluetooth device known to BlueZ.
    """
    _gateway().forget_bluetooth_device(address)
