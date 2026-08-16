import logging
from dataclasses import dataclass
from time import monotonic, sleep
from typing import Any, Literal

import dbus

from ..misc import translate_dbus_errors

logger = logging.getLogger(__name__)


NETWORK_MANAGER_SERVICE = "org.freedesktop.NetworkManager"
NETWORK_MANAGER_PATH = "/org/freedesktop/NetworkManager"
NETWORK_MANAGER_SETTINGS_PATH = "/org/freedesktop/NetworkManager/Settings"
NETWORK_MANAGER_SETTINGS_INTERFACE = "org.freedesktop.NetworkManager.Settings"
NETWORK_MANAGER_SETTINGS_CONNECTION_INTERFACE = (
    "org.freedesktop.NetworkManager.Settings.Connection"
)
NETWORK_MANAGER_DEVICE_INTERFACE = "org.freedesktop.NetworkManager.Device"
NETWORK_MANAGER_WIRELESS_INTERFACE = "org.freedesktop.NetworkManager.Device.Wireless"
NETWORK_MANAGER_ACCESS_POINT_INTERFACE = "org.freedesktop.NetworkManager.AccessPoint"
NETWORK_MANAGER_ACTIVE_CONNECTION_INTERFACE = (
    "org.freedesktop.NetworkManager.Connection.Active"
)

WIFI_IEEE = "802-11-wireless"
WIFI_SECURITY = "802-11-wireless-security"

NM_ACTIVE_CONNECTION_STATE_ACTIVATED = 2
NM_ACTIVE_CONNECTION_STATE_DEACTIVATING = 3
NM_ACTIVE_CONNECTION_STATE_DEACTIVATED = 4

NM_AP_FLAGS_PRIVACY = 0x1

NM_AP_SEC_KEY_MGMT_PSK = 0x100
NM_AP_SEC_KEY_MGMT_802_1X = 0x200
NM_AP_SEC_KEY_MGMT_SAE = 0x400
NM_AP_SEC_KEY_MGMT_OWE = 0x800
NM_AP_SEC_KEY_MGMT_OWE_TM = 0x1000
NM_AP_SEC_KEY_MGMT_EAP_SUITE_B_192 = 0x2000

type WifiAuthentication = Literal["open", "password", "enterprise"]


def _get_wifi_device_paths(bus: dbus.SystemBus) -> list[str]:
    """Return D-Bus object paths of WiFi devices.

    Parameters
    ----------
    `bus` : `dbus.SystemBus`
        Connected D-Bus system bus.

    Returns
    -------
    `list[str]`
        D-Bus object paths of WiFi devices.
    """
    logger.debug("Query NetworkManager to find all WiFi device paths.")

    network_manager_proxy = bus.get_object(NETWORK_MANAGER_SERVICE, NETWORK_MANAGER_PATH)
    object_manager = dbus.Interface(network_manager_proxy, NETWORK_MANAGER_SERVICE)

    device_paths = object_manager.GetDevices()
    wifi_device_paths = []
    for device_path in device_paths:
        device_proxy = bus.get_object(NETWORK_MANAGER_SERVICE, device_path)
        properties = dbus.Interface(device_proxy, dbus.PROPERTIES_IFACE)

        device_type = properties.Get(NETWORK_MANAGER_DEVICE_INTERFACE, "DeviceType")

        if int(device_type) == 2:
            wifi_device_paths.append(str(device_path))

    return wifi_device_paths


def _get_access_point_properties(
    bus: dbus.SystemBus, access_point_path: str
) -> dict[str, Any]:
    """Return the properties of a NetworkManager access point.

    Parameters
    ----------
    `bus` : `dbus.SystemBus`
        Connected D-Bus system bus.

    Returns
    -------
    `dict[str, Any]`
        Access point properties
    """
    access_point_proxy = bus.get_object(
        NETWORK_MANAGER_SERVICE,
        access_point_path,
    )
    properties = dbus.Interface(
        access_point_proxy,
        dbus.PROPERTIES_IFACE,
    )

    return properties.GetAll(NETWORK_MANAGER_ACCESS_POINT_INTERFACE)


def _decode_ssid(value: dbus.Array | dbus.ByteArray) -> str:
    """Decode a D-Bus byte array containing an SSID.

    Parameters
    ----------
    `value` : `dbus.Array` or `dbus.ByteArray`
        D-Bus byte array representing an SSID.

    Returns
    -------
    `str`
        SSID decoded as UTF-8, with invalid byte sequences replaced.
    """
    return bytes(value).decode("utf-8", errors="replace")


def _get_wifi_access_point_path(
    bus: dbus.SystemBus, device_path: str, ssid: str
) -> str | None:
    """Return the object path of an access point matching an SSID.

    Parameters
    ----------
    `bus` : `dbus.SystemBus`
        Connected D-Bus system bus.
    `device_path` : `str`
        Object path of the NetworkManager WiFi device.
    `ssid` : `str`
        SSID of the requested WiFi network.

    Returns
    -------
    `str` or `None`
        Object path of the matching access point, or `None` if it was not found.
    """
    device_proxy = bus.get_object(
        NETWORK_MANAGER_SERVICE,
        device_path,
    )
    wireless = dbus.Interface(
        device_proxy,
        NETWORK_MANAGER_WIRELESS_INTERFACE,
    )

    for access_point_path in wireless.GetAllAccessPoints():
        properties = _get_access_point_properties(
            bus,
            str(access_point_path),
        )

        if _decode_ssid(properties["Ssid"]) == ssid:
            return str(access_point_path)

    return None


def _get_wifi_connection_target(
    bus: dbus.SystemBus,
    ssid: str,
) -> tuple[str, str]:
    """Return the device and access-point paths for an SSID."""
    for device_path in _get_wifi_device_paths(bus):
        access_point_path = _get_wifi_access_point_path(bus, device_path, ssid)

        if access_point_path is not None:
            return device_path, access_point_path

    raise WifiError(f"WiFi network {ssid!r} was not found.")


def _get_wifi_authentication(
    flags: int, wpa_flags: int, rsn_flags: int
) -> WifiAuthentication:
    """Return the authentication method required by an access point.

    Parameters
    ----------
    `flags` : `int`
        General access-point capability flags.
    `wpa_flags` : `int`
        WPA security and authentication flags.
    `rsn_flags` : `int`
        RSN security and authentication flags.

    Returns
    -------
    `WifiAuthentication`
        Authentication method required to connect to the access point.
    """
    security_flags = wpa_flags | rsn_flags
    enterprise_flags = NM_AP_SEC_KEY_MGMT_802_1X | NM_AP_SEC_KEY_MGMT_EAP_SUITE_B_192
    password_flags = NM_AP_SEC_KEY_MGMT_PSK | NM_AP_SEC_KEY_MGMT_SAE
    owe_flags = NM_AP_SEC_KEY_MGMT_OWE | NM_AP_SEC_KEY_MGMT_OWE_TM

    if security_flags & enterprise_flags:
        return "enterprise"

    if security_flags & password_flags:
        return "password"

    if security_flags & owe_flags:
        return "open"

    if flags & NM_AP_FLAGS_PRIVACY:
        return "password"

    return "open"


def _build_wifi_connection_settings(
    ssid: str,
    password: str | None,
    access_point_properties: dict[str, Any],
) -> dbus.Dictionary:
    """Build NetworkManager settings for a new WiFi connection."""
    flags = int(access_point_properties["Flags"])
    wpa_flags = int(access_point_properties["WpaFlags"])
    rsn_flags = int(access_point_properties["RsnFlags"])
    security_flags = wpa_flags | rsn_flags
    authentication = _get_wifi_authentication(flags, wpa_flags, rsn_flags)

    if authentication == "enterprise":
        raise WifiError("Connecting to a new enterprise WiFi network is not supported.")

    if authentication == "password" and password is None:
        raise WifiError(f"WiFi network {ssid!r} requires a password.")

    if authentication == "open" and password is not None:
        raise WifiError(f"WiFi network {ssid!r} does not require a password.")

    personal_flags = NM_AP_SEC_KEY_MGMT_PSK | NM_AP_SEC_KEY_MGMT_SAE
    if authentication == "password" and not security_flags & personal_flags:
        raise WifiError("Connecting to a WEP WiFi network is not supported.")

    settings = dbus.Dictionary(
        {
            "connection": dbus.Dictionary(
                {
                    "id": dbus.String(ssid),
                    "type": dbus.String(WIFI_IEEE),
                },
                signature="sv",
            ),
            WIFI_IEEE: dbus.Dictionary(
                {"ssid": dbus.ByteArray(ssid.encode())},
                signature="sv",
            ),
        },
        signature="sa{sv}",
    )

    if authentication == "password":
        assert password is not None
        key_management = (
            "sae"
            if security_flags & NM_AP_SEC_KEY_MGMT_SAE
            and not security_flags & NM_AP_SEC_KEY_MGMT_PSK
            else "wpa-psk"
        )
        settings[WIFI_SECURITY] = dbus.Dictionary(
            {
                "key-mgmt": dbus.String(key_management),
                "psk": dbus.String(password),
            },
            signature="sv",
        )
    elif security_flags & (NM_AP_SEC_KEY_MGMT_OWE | NM_AP_SEC_KEY_MGMT_OWE_TM):
        settings[WIFI_SECURITY] = dbus.Dictionary(
            {"key-mgmt": dbus.String("owe")},
            signature="sv",
        )

    return settings


def _wait_for_wifi_connection(
    bus: dbus.SystemBus,
    active_connection_path: str,
    timeout: float = 30.0,
) -> None:
    """Wait until a NetworkManager connection is activated."""
    active_connection_proxy = bus.get_object(
        NETWORK_MANAGER_SERVICE,
        active_connection_path,
    )
    properties = dbus.Interface(
        active_connection_proxy,
        dbus.PROPERTIES_IFACE,
    )
    deadline = monotonic() + timeout

    while True:
        state = int(
            properties.Get(
                NETWORK_MANAGER_ACTIVE_CONNECTION_INTERFACE,
                "State",
            )
        )

        if state == NM_ACTIVE_CONNECTION_STATE_ACTIVATED:
            return

        if state in {
            NM_ACTIVE_CONNECTION_STATE_DEACTIVATING,
            NM_ACTIVE_CONNECTION_STATE_DEACTIVATED,
        }:
            raise WifiError("WiFi connection failed.")

        if monotonic() >= deadline:
            raise WifiError("WiFi connection timed out.")

        sleep(0.2)


# public API ---------------------------------------------------------------------------


class WifiError(RuntimeError):
    """Indicate that a WiFi operation failed."""


@dataclass(frozen=True, slots=True)  # creates an immutable datatype
class WifiNetwork:
    """Represent a visible WiFi network.

    Parameters
    ----------
    `ssid` : `str`
        Network name.
    `signal` : `int`
        Signal strength from 0 to 100.
    `authentication` : `WifiAuthentication`
        Authentication method required to connect to the network.
    `connected` : `bool`
        Whether this network is currently connected.
    """

    ssid: str
    signal: int
    authentication: WifiAuthentication
    connected: bool


@dataclass(frozen=True, slots=True)  # creates an immutable datatype
class SavedWifiProfile:
    """Represent a saved NetworkManager WiFi profile.

    Parameters
    ----------
    `uuid` : `str`
        Unique identifier of the NetworkManager connection profile.
    `profile_name` : `str`
        Human-readable name of the connection profile.
    `ssid` : `str`
        SSID associated with the connection profile.
    """

    uuid: str
    profile_name: str
    ssid: str


# listings


@translate_dbus_errors(WifiError)
def wifi_is_enabled() -> bool:
    """Return whether WiFi is enabled.

    Returns
    -------
    `bool`
        `True` if WiFi is enabled; otherwise, `False`.
    """
    logger.debug("Query NetworkManager for wifi state via D-Bus.")

    bus = dbus.SystemBus()
    network_manager_proxy = bus.get_object(NETWORK_MANAGER_SERVICE, NETWORK_MANAGER_PATH)
    properties = dbus.Interface(network_manager_proxy, dbus.PROPERTIES_IFACE)
    enabled = properties.Get(NETWORK_MANAGER_SERVICE, "WirelessEnabled")

    return bool(enabled)


@translate_dbus_errors(WifiError)
def list_visible_wifi_networks() -> list[WifiNetwork]:
    """List all visible WiFi networks.

    Returns
    -------
    `list[WifiNetwork]`
        Visible WiFi networks reported by NetworkManager.
    """
    logger.debug("Query NetworkManager to list all visible WiFi networks.")

    networks: dict[str, WifiNetwork] = {}
    bus = dbus.SystemBus()
    for device_path in _get_wifi_device_paths(bus):
        device_proxy = bus.get_object(NETWORK_MANAGER_SERVICE, device_path)

        wireless = dbus.Interface(device_proxy, NETWORK_MANAGER_WIRELESS_INTERFACE)

        device_properties = dbus.Interface(device_proxy, dbus.PROPERTIES_IFACE)
        active_access_point = device_properties.Get(
            NETWORK_MANAGER_WIRELESS_INTERFACE, "ActiveAccessPoint"
        )

        access_point_paths = wireless.GetAllAccessPoints()
        for access_point_path in access_point_paths:
            properties = _get_access_point_properties(bus, str(access_point_path))
            ssid = _decode_ssid(properties["Ssid"])
            if not ssid:
                continue

            current_network: WifiNetwork | None = networks.get(ssid)
            candidate = WifiNetwork(
                ssid=ssid,
                signal=int(properties["Strength"]),
                authentication=_get_wifi_authentication(
                    int(properties["Flags"]),
                    int(properties["WpaFlags"]),
                    int(properties["RsnFlags"]),
                ),
                connected=str(access_point_path) == str(active_access_point),
            )

            if current_network is None:
                networks[ssid] = candidate
                continue

            if current_network.connected:
                continue

            if candidate.connected or current_network.signal < candidate.signal:
                networks[ssid] = candidate

    return list(networks.values())


def show_connected_wifi_network() -> WifiNetwork | None:
    """Return the currently connected WiFi network.

    Returns
    -------
    `WifiNetwork` or `None`
        Connected WiFi network, or `None` if no network is connected.
    """
    logger.debug("Call list_visible_wifi_networks to query the connected WiFi network.")

    return next(
        (network for network in list_visible_wifi_networks() if network.connected),
        None,
    )


@translate_dbus_errors(WifiError)
def list_saved_wifi_networks() -> list[SavedWifiProfile]:
    """List saved NetworkManager WiFi profiles."""
    logger.debug("Query saved WiFi profiles via D-Bus.")

    profiles: list[SavedWifiProfile] = []

    bus = dbus.SystemBus()
    settings_proxy = bus.get_object(
        NETWORK_MANAGER_SERVICE,
        NETWORK_MANAGER_SETTINGS_PATH,
    )
    settings = dbus.Interface(settings_proxy, NETWORK_MANAGER_SETTINGS_INTERFACE)
    connection_paths = settings.ListConnections()

    for connection_path in connection_paths:
        connection_proxy = bus.get_object(NETWORK_MANAGER_SERVICE, connection_path)
        connection = dbus.Interface(
            connection_proxy,
            NETWORK_MANAGER_SETTINGS_CONNECTION_INTERFACE,
        )
        profile_settings = connection.GetSettings()

        connection_settings = profile_settings["connection"]

        if str(connection_settings["type"]) != WIFI_IEEE:
            continue

        wifi_settings = profile_settings[WIFI_IEEE]

        profiles.append(
            SavedWifiProfile(
                uuid=str(connection_settings["uuid"]),
                profile_name=str(connection_settings["id"]),
                ssid=_decode_ssid(wifi_settings["ssid"]),
            )
        )

    return profiles


# control


@translate_dbus_errors(WifiError)
def enable_wifi(enable: bool) -> None:
    """Enable or disable WiFi.

    Parameters
    ----------
    `enable` : `bool`
        Whether to enable (`True`) or disable (`False`) WiFi.
    """
    logger.debug("Set NetworkManager WiFi state via D-Bus.")

    bus = dbus.SystemBus()
    network_manager_proxy = bus.get_object(NETWORK_MANAGER_SERVICE, NETWORK_MANAGER_PATH)
    properties = dbus.Interface(network_manager_proxy, dbus.PROPERTIES_IFACE)

    properties.Set(NETWORK_MANAGER_SERVICE, "WirelessEnabled", dbus.Boolean(enable))


@translate_dbus_errors(WifiError)
def scan_wifi_networks() -> None:
    """Scan for visible WiFi networks."""
    logger.debug("Request a WiFi scan via D-Bus.")

    bus = dbus.SystemBus()
    for device_path in _get_wifi_device_paths(bus):
        device_proxy = bus.get_object(NETWORK_MANAGER_SERVICE, device_path)
        properties = dbus.Interface(device_proxy, dbus.PROPERTIES_IFACE)
        wireless = dbus.Interface(device_proxy, NETWORK_MANAGER_WIRELESS_INTERFACE)

        previous_last_scan = properties.Get(
            NETWORK_MANAGER_WIRELESS_INTERFACE, "LastScan"
        )
        wireless.RequestScan(dbus.Dictionary({}, signature="sv"))

        deadline = monotonic() + 10.0

        while (
            properties.Get(NETWORK_MANAGER_WIRELESS_INTERFACE, "LastScan")
            == previous_last_scan
        ):
            if monotonic() >= deadline:
                raise WifiError("WiFi scan timed out.")
            sleep(0.2)


@translate_dbus_errors(WifiError)
def connect_wifi_network(ssid: str, password: str | None = None) -> None:
    """Connect to a WiFi network.

    Parameters
    ----------
    `ssid` : `str`
        SSID of the WiFi network.
    `password` : `str` or `None`, optional
        Password of the WiFi network, or `None` to use stored credentials.
    """
    logger.debug("Connect to WiFi network %r via D-Bus.", ssid)

    bus = dbus.SystemBus()
    device_path, access_point_path = _get_wifi_connection_target(bus, ssid)
    saved_profile = next(
        (profile for profile in list_saved_wifi_networks() if profile.ssid == ssid),
        None,
    )

    network_manager_proxy = bus.get_object(
        NETWORK_MANAGER_SERVICE,
        NETWORK_MANAGER_PATH,
    )
    network_manager = dbus.Interface(
        network_manager_proxy,
        NETWORK_MANAGER_SERVICE,
    )

    if saved_profile is not None:
        if password is not None:
            raise WifiError(
                f"WiFi network {ssid!r} already has a saved profile; "
                "connect without a password or forget the profile first."
            )

        settings_proxy = bus.get_object(
            NETWORK_MANAGER_SERVICE,
            NETWORK_MANAGER_SETTINGS_PATH,
        )
        settings = dbus.Interface(
            settings_proxy,
            NETWORK_MANAGER_SETTINGS_INTERFACE,
        )
        connection_path = settings.GetConnectionByUuid(saved_profile.uuid)
        active_connection_path = network_manager.ActivateConnection(
            connection_path,
            device_path,
            access_point_path,
        )
        _wait_for_wifi_connection(bus, str(active_connection_path))
        return

    access_point_properties = _get_access_point_properties(
        bus,
        access_point_path,
    )
    connection_settings = _build_wifi_connection_settings(
        ssid,
        password,
        access_point_properties,
    )

    _, active_connection_path, _ = network_manager.AddAndActivateConnection2(
        connection_settings,
        device_path,
        access_point_path,
        dbus.Dictionary(
            {"persist": dbus.String("disk")},
            signature="sv",
        ),
    )
    _wait_for_wifi_connection(bus, str(active_connection_path))


@translate_dbus_errors(WifiError)
def disconnect_wifi_network() -> None:
    """Disconnect the active WiFi network."""
    logger.debug("Disconnect the active WiFi network via D-Bus.")

    bus = dbus.SystemBus()
    for device_path in _get_wifi_device_paths(bus):
        device_proxy = bus.get_object(NETWORK_MANAGER_SERVICE, device_path)
        properties = dbus.Interface(device_proxy, dbus.PROPERTIES_IFACE)
        active_connection = properties.Get(
            NETWORK_MANAGER_DEVICE_INTERFACE,
            "ActiveConnection",
        )

        if str(active_connection) == "/":
            continue

        device = dbus.Interface(device_proxy, NETWORK_MANAGER_DEVICE_INTERFACE)
        device.Disconnect()
        return

    raise WifiError("No active WiFi connection was found.")


@translate_dbus_errors(WifiError)
def forget_wifi(uuid: str) -> None:
    """Delete a saved WiFi connection profile.

    Parameters
    ----------
    `uuid` : `str`
        Unique identifier of the NetworkManager connection profile.
    """
    logger.debug("Delete WiFi connection profile %r via D-Bus.", uuid)

    bus = dbus.SystemBus()
    settings_proxy = bus.get_object(
        NETWORK_MANAGER_SERVICE,
        NETWORK_MANAGER_SETTINGS_PATH,
    )
    settings = dbus.Interface(
        settings_proxy,
        NETWORK_MANAGER_SETTINGS_INTERFACE,
    )
    connection_path = settings.GetConnectionByUuid(uuid)
    connection_proxy = bus.get_object(
        NETWORK_MANAGER_SERVICE,
        connection_path,
    )
    connection = dbus.Interface(
        connection_proxy,
        NETWORK_MANAGER_SETTINGS_CONNECTION_INTERFACE,
    )
    connection.Delete()
