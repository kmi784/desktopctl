import logging
from dataclasses import dataclass
from time import sleep

import dbus

from desktopctl.misc import translate_dbus_errors

logger = logging.getLogger(__name__)


BLUEZ_SERVICE = "org.bluez"
ADAPTER_PATH = "/org/bluez/hci0"
BLUEZ_ADAPTER_INTERFACE = "org.bluez.Adapter1"
BLUEZ_DEVICE_INTERFACE = "org.bluez.Device1"
DBUS_OBJECT_MANAGER_INTERFACE = "org.freedesktop.DBus.ObjectManager"


def _get_bluetooth_device_path(bus: dbus.SystemBus, address: str) -> str:
    """Return the object path of a discovered Bluetooth device."""
    bluez_proxy = bus.get_object(BLUEZ_SERVICE, "/")
    object_manager = dbus.Interface(
        bluez_proxy,
        DBUS_OBJECT_MANAGER_INTERFACE,
    )

    for device_path, interfaces in object_manager.GetManagedObjects().items():
        properties = interfaces.get(BLUEZ_DEVICE_INTERFACE)

        if properties is None:
            continue

        if str(properties["Address"]).casefold() == address.casefold():
            return str(device_path)

    raise BluetoothError(
        f"Bluetooth device {address!r} was not found. Scan for devices first."
    )


# public API ---------------------------------------------------------------------------


class BluetoothError(RuntimeError):
    """Indicate that a Bluetooth operation failed."""


@dataclass(frozen=True, slots=True)
class BluetoothDevice:
    """Represent a Bluetooth device.

    Parameters
    ----------
    `address` : `str`
        Bluetooth device address.
    `name` : `str | None`
        Human-readable device name, or `None` if unavailable.
    `rssi` : `int | None`
        Received signal strength indicator (RSSI), or `None` if unavailable.
    `battery` : `int | None`
        Battery percentage from 0 to 100, or `None` if unavailable.
    `paired` : `bool`
        Whether the device is paired.
    `connected` : `bool`
        Whether the device is currently connected.
    """

    address: str
    name: str | None
    rssi: int | None
    battery: int | None
    paired: bool
    connected: bool


# listings


@translate_dbus_errors(BluetoothError)
def bluetooth_is_enabled() -> bool:
    """Return whether Bluetooth is enabled.

    Returns
    -------
    `bool`
        `True` if Bluetooth is enabled; otherwise, `False`.
    """
    logger.debug("Query Bluetooth adapter power state via D-Bus.")

    bus = dbus.SystemBus()

    # Proxy object representing the Bluetooth adapter managed by BlueZ.
    adapter_proxy = bus.get_object(BLUEZ_SERVICE, ADAPTER_PATH)

    # Proxy for the standard D-Bus properties interface.
    properties = dbus.Interface(adapter_proxy, dbus.PROPERTIES_IFACE)

    # Power-state property of the Bluetooth adapter.
    powered = properties.Get(BLUEZ_ADAPTER_INTERFACE, "Powered")

    return bool(powered)


@translate_dbus_errors(BluetoothError)
def list_visible_bluetooth_devices() -> list[BluetoothDevice]:
    """List all visible Bluetooth devices.

    Returns
    -------
    `list[BluetoothDevice]`
        Visible Bluetooth devices reported by BlueZ.
    """
    logger.debug("Query visible Bluetooth devices via D-Bus.")

    bus = dbus.SystemBus()

    # Proxy object representing the root of the BlueZ object tree.
    bluez_proxy = bus.get_object(BLUEZ_SERVICE, "/")

    object_manager = dbus.Interface(bluez_proxy, DBUS_OBJECT_MANAGER_INTERFACE)

    managed_objects = object_manager.GetManagedObjects()

    devices = []
    for interfaces in managed_objects.values():
        device_properties = interfaces.get(BLUEZ_DEVICE_INTERFACE)

        if device_properties is None:
            continue

        battery_properties = interfaces.get("org.bluez.Battery1")
        battery = None
        if battery_properties is not None:
            percentage = battery_properties.get("Percentage")
            if percentage is not None:
                battery = int(percentage)

        name = device_properties.get("Alias") or device_properties.get("Name")
        rssi = device_properties.get("RSSI")

        devices.append(
            BluetoothDevice(
                address=str(device_properties["Address"]),
                name=None if name is None else str(name),
                rssi=None if rssi is None else int(rssi),
                battery=battery,
                paired=bool(device_properties["Paired"]),
                connected=bool(device_properties["Connected"]),
            )
        )

    return devices


def list_connected_bluetooth_devices() -> list[BluetoothDevice]:
    """List all connected Bluetooth devices.

    Returns
    -------
    `list[BluetoothDevice]`
        Connected Bluetooth devices reported by BlueZ.
    """
    logger.debug(
        "Call list_visible_bluetooth_devices to query connected Bluetooth devices."
    )

    devices = []
    for device in list_visible_bluetooth_devices():
        if device.connected:
            devices.append(device)

    return devices


def list_paired_bluetooth_devices() -> list[BluetoothDevice]:
    """List all paired Bluetooth devices.

    Returns
    -------
    `list[BluetoothDevice]`
        Paired Bluetooth devices reported by BlueZ.
    """
    logger.debug(
        "Call list_visible_bluetooth_devices to query paired Bluetooth devices."
    )

    devices = []
    for device in list_visible_bluetooth_devices():
        if device.paired:
            devices.append(device)

    return devices


# control


@translate_dbus_errors(BluetoothError)
def enable_bluetooth(enable: bool) -> None:
    """Enable or disable Bluetooth.

    Parameters
    ----------
    `enable` : `bool`
        Whether to enable (`True`) or disable (`False`) Bluetooth.
    """
    logger.debug("Set Bluetooth adapter power state via D-Bus.")

    bus = dbus.SystemBus()
    adapter_proxy = bus.get_object(BLUEZ_SERVICE, ADAPTER_PATH)
    properties = dbus.Interface(adapter_proxy, dbus.PROPERTIES_IFACE)

    properties.Set(BLUEZ_ADAPTER_INTERFACE, "Powered", dbus.Boolean(enable))


@translate_dbus_errors(BluetoothError)
def scan_bluetooth_devices(duration: int = 10) -> None:
    """Scan for nearby Bluetooth devices.

    Parameters
    ----------
    `duration` : `int`, optional
        Scan duration in seconds.
    """
    logger.debug("Scan for Bluetooth devices via D-Bus.")

    bus = dbus.SystemBus()
    adapter_proxy = bus.get_object(BLUEZ_SERVICE, ADAPTER_PATH)
    adapter = dbus.Interface(adapter_proxy, BLUEZ_ADAPTER_INTERFACE)
    adapter.StartDiscovery()

    try:
        sleep(duration)
    finally:
        adapter.StopDiscovery()


@translate_dbus_errors(BluetoothError)
def pair_bluetooth_device(address: str) -> None:
    """Pair a Bluetooth device using the system agent.

    Parameters
    ----------
    `address` : `str`
        Address of a Bluetooth device discovered by BlueZ.
    """
    logger.debug("Pair Bluetooth device %s via D-Bus.", address)

    bus = dbus.SystemBus()
    device_path = _get_bluetooth_device_path(bus, address)
    device_proxy = bus.get_object(BLUEZ_SERVICE, device_path)
    device = dbus.Interface(device_proxy, BLUEZ_DEVICE_INTERFACE)
    device.Pair()


@translate_dbus_errors(BluetoothError)
def connect_bluetooth_device(address: str) -> None:
    """Connect a paired Bluetooth device.

    Parameters
    ----------
    `address` : `str`
        Address of a Bluetooth device known to BlueZ.
    """
    logger.debug("Connect Bluetooth device %s via D-Bus.", address)

    bus = dbus.SystemBus()
    device_path = _get_bluetooth_device_path(bus, address)
    device_proxy = bus.get_object(BLUEZ_SERVICE, device_path)
    device = dbus.Interface(device_proxy, BLUEZ_DEVICE_INTERFACE)
    device.Connect()


@translate_dbus_errors(BluetoothError)
def disconnect_bluetooth_device(address: str) -> None:
    """Disconnect a Bluetooth device.

    Parameters
    ----------
    `address` : `str`
        Address of a Bluetooth device known to BlueZ.
    """
    logger.debug("Disconnect Bluetooth device %s via D-Bus.", address)

    bus = dbus.SystemBus()
    device_path = _get_bluetooth_device_path(bus, address)
    device_proxy = bus.get_object(BLUEZ_SERVICE, device_path)
    device = dbus.Interface(device_proxy, BLUEZ_DEVICE_INTERFACE)
    device.Disconnect()


@translate_dbus_errors(BluetoothError)
def forget_bluetooth_device(address: str) -> None:
    """Forget a paired Bluetooth device.

    Parameters
    ----------
    `address` : `str`
        Address of a Bluetooth device known to BlueZ.
    """
    logger.debug("Forget Bluetooth device %s via D-Bus.", address)

    bus = dbus.SystemBus()
    device_path = _get_bluetooth_device_path(bus, address)
    adapter_proxy = bus.get_object(BLUEZ_SERVICE, ADAPTER_PATH)
    adapter = dbus.Interface(adapter_proxy, BLUEZ_ADAPTER_INTERFACE)
    adapter.RemoveDevice(device_path)
