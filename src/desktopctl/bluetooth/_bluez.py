import logging
from dataclasses import dataclass
from time import sleep

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

from .bluez_agent import (
    BLUEZ_AGENT_CAPABILITY,
    BLUEZ_AGENT_MANAGER_INTERFACE,
    BLUEZ_AGENT_MANAGER_PATH,
    BLUEZ_AGENT_PATH,
    BlueZAgent,
)

logger = logging.getLogger(__name__)


BLUEZ_SERVICE = "org.bluez"
BLUEZ_ROOT_PATH = "/"
ADAPTER_PATH = "/org/bluez/hci0"
BLUEZ_ADAPTER_INTERFACE = "org.bluez.Adapter1"
BLUEZ_BATTERY_INTERFACE = "org.bluez.Battery1"
BLUEZ_DEVICE_INTERFACE = "org.bluez.Device1"
DBUS_OBJECT_MANAGER_INTERFACE = "org.freedesktop.DBus.ObjectManager"
PAIRING_TIMEOUT = 60


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


@dataclass(frozen=True, slots=True)
class _ManagedBluetoothDevice:
    """Associate a Bluetooth device with its BlueZ object paths.

    Parameters
    ----------
    `path` : `str`
        D-Bus object path of the Bluetooth device.
    `adapter_path` : `str`
        D-Bus object path of the adapter managing the device.
    `device` : `BluetoothDevice`
        Normalized public device data.
    """

    path: str
    adapter_path: str
    device: BluetoothDevice


class _BlueZGateway:
    """Provide focused access to BlueZ's adapter and device D-Bus APIs.

    One gateway represents one backend operation and reuses the supplied bus and
    Object Manager data instead of resolving the same BlueZ objects repeatedly.

    Parameters
    ----------
    `bus` : `dbus.SystemBus`
        Connected D-Bus system bus.
    """

    def __init__(self, bus: dbus.SystemBus) -> None:
        self._bus = bus
        self._proxies: dict[str, object] = {}

    def _interface(self, path: str, interface_name: str) -> dbus.Interface:
        """Return a D-Bus interface for a BlueZ object."""
        if path not in self._proxies:
            self._proxies[path] = self._bus.get_object(BLUEZ_SERVICE, path)

        proxy = self._proxies[path]
        return dbus.Interface(proxy, interface_name)

    def _properties(self, path: str) -> dbus.Interface:
        """Return the standard properties interface for an object."""
        return self._interface(path, dbus.PROPERTIES_IFACE)

    def _managed_objects(self) -> dict:
        """Return a snapshot of BlueZ's managed D-Bus objects."""
        return self._interface(
            BLUEZ_ROOT_PATH,
            DBUS_OBJECT_MANAGER_INTERFACE,
        ).GetManagedObjects()

    def _default_adapter_path(self) -> str:
        """Return the preferred available Bluetooth adapter path."""
        adapter_paths = sorted(
            str(path)
            for path, interfaces in self._managed_objects().items()
            if BLUEZ_ADAPTER_INTERFACE in interfaces
        )

        if ADAPTER_PATH in adapter_paths:
            return ADAPTER_PATH

        if adapter_paths:
            return adapter_paths[0]

        raise BluetoothError("No Bluetooth adapter was found.")

    def _normalize_device(
        self,
        path: str,
        interfaces: dict,
    ) -> _ManagedBluetoothDevice | None:
        """Return normalized data for a managed BlueZ device object."""
        device_properties = interfaces.get(BLUEZ_DEVICE_INTERFACE)
        if device_properties is None:
            return None

        battery = None
        battery_properties = interfaces.get(BLUEZ_BATTERY_INTERFACE)
        if battery_properties is not None:
            percentage = battery_properties.get("Percentage")
            if percentage is not None:
                battery = int(percentage)

        name = device_properties.get("Alias") or device_properties.get("Name")
        rssi = device_properties.get("RSSI")
        adapter_path = device_properties.get("Adapter")

        if adapter_path is None:
            adapter_path = path.rpartition("/dev_")[0]

        return _ManagedBluetoothDevice(
            path=path,
            adapter_path=str(adapter_path),
            device=BluetoothDevice(
                address=str(device_properties["Address"]),
                name=None if name is None else str(name),
                rssi=None if rssi is None else int(rssi),
                battery=battery,
                paired=bool(device_properties["Paired"]),
                connected=bool(device_properties["Connected"]),
            ),
        )

    def _get_devices(self) -> list[_ManagedBluetoothDevice]:
        """Return normalized data for all managed BlueZ devices."""
        devices = []

        for path, interfaces in self._managed_objects().items():
            device = self._normalize_device(str(path), interfaces)
            if device is not None:
                devices.append(device)

        return devices

    def _get_device(self, address: str) -> _ManagedBluetoothDevice:
        """Return a managed Bluetooth device matching an address."""
        for device in self._get_devices():
            if device.device.address.casefold() == address.casefold():
                return device

        raise BluetoothError(
            f"Bluetooth device {address!r} was not found. Scan for devices first."
        )

    def bluetooth_is_enabled(self) -> bool:
        """Return whether the preferred Bluetooth adapter is powered."""
        logger.debug("Query Bluetooth adapter power state via D-Bus.")
        powered = self._properties(self._default_adapter_path()).Get(
            BLUEZ_ADAPTER_INTERFACE,
            "Powered",
        )
        return bool(powered)

    def list_visible_bluetooth_devices(self) -> list[BluetoothDevice]:
        """Return all devices currently managed by BlueZ."""
        logger.debug("Query visible Bluetooth devices via D-Bus.")
        return [managed.device for managed in self._get_devices()]

    def enable_bluetooth(self, enable: bool) -> None:
        """Enable or disable the preferred Bluetooth adapter."""
        logger.debug("Set Bluetooth adapter power state via D-Bus.")
        self._properties(self._default_adapter_path()).Set(
            BLUEZ_ADAPTER_INTERFACE,
            "Powered",
            dbus.Boolean(enable),
        )

    def scan_bluetooth_devices(self, duration: int) -> None:
        """Scan for nearby Bluetooth devices."""
        logger.debug("Scan for Bluetooth devices via D-Bus.")
        adapter = self._interface(
            self._default_adapter_path(),
            BLUEZ_ADAPTER_INTERFACE,
        )
        adapter.StartDiscovery()

        try:
            sleep(duration)
        finally:
            adapter.StopDiscovery()

    def connect_bluetooth_device(self, address: str) -> None:
        """Connect a paired Bluetooth device."""
        logger.debug("Connect Bluetooth device %s via D-Bus.", address)
        device = self._get_device(address)
        self._interface(device.path, BLUEZ_DEVICE_INTERFACE).Connect()

    def disconnect_bluetooth_device(self, address: str) -> None:
        """Disconnect a Bluetooth device."""
        logger.debug("Disconnect Bluetooth device %s via D-Bus.", address)
        device = self._get_device(address)
        self._interface(device.path, BLUEZ_DEVICE_INTERFACE).Disconnect()

    def forget_bluetooth_device(self, address: str) -> None:
        """Forget a paired Bluetooth device on its managing adapter."""
        logger.debug("Forget Bluetooth device %s via D-Bus.", address)
        device = self._get_device(address)
        self._interface(
            device.adapter_path,
            BLUEZ_ADAPTER_INTERFACE,
        ).RemoveDevice(device.path)


class _BlueZPairingSession:
    """Manage the private bus and temporary agent for one pairing operation.

    Parameters
    ----------
    `address` : `str`
        Address of the Bluetooth device to pair.
    """

    def __init__(self, address: str) -> None:
        dbus_main_loop = DBusGMainLoop()
        self._bus = dbus.SystemBus(private=True, mainloop=dbus_main_loop)
        self._gateway = _BlueZGateway(self._bus)
        self._address = address
        self._agent: BlueZAgent | None = None
        self._agent_manager: dbus.Interface | None = None
        self._agent_registered = False

    def __enter__(self) -> "_BlueZPairingSession":
        return self

    def __exit__(self, _error_type, _error, _traceback) -> None:
        self._close()

    def _register_agent(self, device_path: str) -> None:
        """Register a temporary pairing agent for the selected device."""
        self._agent = BlueZAgent(self._bus, device_path)
        self._agent_manager = self._gateway._interface(
            BLUEZ_AGENT_MANAGER_PATH,
            BLUEZ_AGENT_MANAGER_INTERFACE,
        )
        self._agent_manager.RegisterAgent(
            BLUEZ_AGENT_PATH,
            BLUEZ_AGENT_CAPABILITY,
        )
        self._agent_registered = True

    def _run_pairing(self, device: dbus.Interface) -> None:
        """Run the GLib main loop until the asynchronous pairing finishes."""
        main_loop = GLib.MainLoop()
        pairing_finished = False
        pairing_error = None

        def _finish_pairing() -> None:
            nonlocal pairing_finished
            pairing_finished = True
            main_loop.quit()

        def _fail_pairing(error: dbus.exceptions.DBusException) -> None:
            nonlocal pairing_error, pairing_finished
            pairing_error = error
            pairing_finished = True
            main_loop.quit()

        device.Pair(
            reply_handler=_finish_pairing,
            error_handler=_fail_pairing,
            timeout=PAIRING_TIMEOUT,
        )

        if not pairing_finished:
            main_loop.run()

        if pairing_error is not None:
            raise pairing_error

    def _trust_device(self, properties: dbus.Interface) -> None:
        """Mark the paired device as trusted."""
        properties.Set(
            BLUEZ_DEVICE_INTERFACE,
            "Trusted",
            dbus.Boolean(True),
        )

    def _close(self) -> None:
        """Unregister the temporary agent and close its private bus."""
        if self._agent_registered:
            assert self._agent_manager is not None
            try:
                self._agent_manager.UnregisterAgent(BLUEZ_AGENT_PATH)
            except dbus.exceptions.DBusException:
                logger.warning(
                    "Failed to unregister the Bluetooth pairing agent.",
                    exc_info=True,
                )

        if self._agent is not None:
            self._agent.remove_from_connection()

        self._bus.close()

    def pair(self) -> None:
        """Pair and trust the selected Bluetooth device."""
        logger.debug("Pair Bluetooth device %s via D-Bus.", self._address)
        managed_device = self._gateway._get_device(self._address)
        device = self._gateway._interface(
            managed_device.path,
            BLUEZ_DEVICE_INTERFACE,
        )
        properties = self._gateway._properties(managed_device.path)

        paired = bool(properties.Get(BLUEZ_DEVICE_INTERFACE, "Paired"))
        bonded = bool(properties.Get(BLUEZ_DEVICE_INTERFACE, "Bonded"))
        if paired and bonded:
            self._trust_device(properties)
            return

        self._register_agent(managed_device.path)
        self._run_pairing(device)

        paired = bool(properties.Get(BLUEZ_DEVICE_INTERFACE, "Paired"))
        bonded = bool(properties.Get(BLUEZ_DEVICE_INTERFACE, "Bonded"))
        if not paired or not bonded:
            raise BluetoothError(
                f"Bluetooth device {self._address!r} was not paired permanently."
            )

        self._trust_device(properties)
