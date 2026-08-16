import logging
from dataclasses import dataclass
from time import sleep

import dbus

logger = logging.getLogger(__name__)


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


def bluetooth_is_enabled() -> bool:
    """Return whether Bluetooth is enabled.

    Returns
    -------
    `bool`
        `True` if Bluetooth is enabled; otherwise, `False`.
    """
    logger.debug("Query Bluetooth adapter power state via D-Bus.")

    try:
        bus = dbus.SystemBus()

        # Proxy object representing the Bluetooth adapter managed by BlueZ.
        adapter_proxy = bus.get_object("org.bluez", "/org/bluez/hci0")

        # Proxy for the standard D-Bus properties interface.
        properties = dbus.Interface(adapter_proxy, dbus.PROPERTIES_IFACE)

        # Power-state property of the Bluetooth adapter.
        powered = properties.Get("org.bluez.Adapter1", "Powered")

    except dbus.exceptions.DBusException as error:
        raise BluetoothError(str(error)) from error

    return bool(powered)


def list_visible_bluetooth_devices() -> list[BluetoothDevice]:
    """List all visible Bluetooth devices.

    Returns
    -------
    `list[BluetoothDevice]`
        Visible Bluetooth devices reported by BlueZ.
    """
    logger.debug("Query visible Bluetooth devices via D-Bus.")

    try:
        bus = dbus.SystemBus()

        # Proxy object representing the root of the BlueZ object tree.
        bluez_proxy = bus.get_object("org.bluez", "/")

        object_manager = dbus.Interface(
            bluez_proxy, "org.freedesktop.DBus.ObjectManager"
        )

        managed_objects = object_manager.GetManagedObjects()
    except dbus.exceptions.DBusException as error:
        raise BluetoothError(str(error)) from error

    devices = []
    for interfaces in managed_objects.values():
        device_properties = interfaces.get("org.bluez.Device1")

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
    logger.debug("Query connected Bluetooth devices via D-Bus.")

    devices = []
    for device in list_visible_bluetooth_devices():
        if device.connected:
            devices.append(device)

    return devices


def list_paired_bluetooth_devices() -> list[BluetoothDevice]:
    """List all paired Bluetooth devices.

    Returns
    -------
    `list[BluetoothDevice | None]`
        Paired Bluetooth devices reported by BlueZ.
    """
    logger.debug("Query paired Bluetooth devices via D-Bus.")

    devices = []
    for device in list_visible_bluetooth_devices():
        if device.paired:
            devices.append(device)

    return devices


# control


def enable_bluetooth(enable: bool) -> None:
    """Enable or disable Bluetooth.

    Parameters
    ----------
    `enable` : `bool`
        Whether to enable (`True`) or disable (`False`) Bluetooth.
    """
    logger.debug("Set Bluetooth adapter power state via D-Bus.")

    try:
        bus = dbus.SystemBus()
        adapter_proxy = bus.get_object("org.bluez", "/org/bluez/hci0")
        properties = dbus.Interface(adapter_proxy, dbus.PROPERTIES_IFACE)

        properties.Set("org.bluez.Adapter1", "Powered", dbus.Boolean(enable))

    except dbus.exceptions.DBusException as error:
        raise BluetoothError(str(error)) from error


def scan_bluetooth_devices(duration: int = 10) -> None:
    """Scan for nearby Bluetooth devices.

    Parameters
    ----------
    `duration` : `int`, optional
        Scan duration in seconds.
    """
    logger.debug("Scan for Bluetooth devices via D-Bus.")

    try:
        bus = dbus.SystemBus()
        adapter_proxy = bus.get_object("org.bluez", "/org/bluez/hci0")
        adapter = dbus.Interface(adapter_proxy, "org.bluez.Adapter1")
        adapter.StartDiscovery()

        try:
            sleep(duration)
        finally:
            adapter.StopDiscovery()

    except dbus.exceptions.DBusException as error:
        raise BluetoothError(str(error)) from error
