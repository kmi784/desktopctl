import logging
from dataclasses import dataclass
from time import monotonic, sleep
from typing import Literal

import dbus

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

NM_DEVICE_TYPE_WIFI = 2

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


class WifiError(RuntimeError):
    """Indicate that a WiFi operation failed."""


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
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


@dataclass(frozen=True, slots=True)
class _WifiAccessPoint:
    """Represent the NetworkManager data needed for one access point.

    Parameters
    ----------
    `path` : `str`
        D-Bus object path of the access point.
    `device_path` : `str`
        D-Bus object path of the WiFi device that reported it.
    `ssid` : `str`
        Network name.
    `signal` : `int`
        Signal strength from 0 to 100.
    `flags` : `int`
        General access-point capability flags.
    `wpa_flags` : `int`
        WPA security and authentication flags.
    `rsn_flags` : `int`
        RSN security and authentication flags.
    `connected` : `bool`
        Whether the access point is active on its WiFi device.
    """

    path: str
    device_path: str
    ssid: str
    signal: int
    flags: int
    wpa_flags: int
    rsn_flags: int
    connected: bool

    @property
    def authentication(self) -> WifiAuthentication:
        """Return the authentication method of the access point."""
        return _get_wifi_authentication(self.flags, self.wpa_flags, self.rsn_flags)

    def to_network(self) -> WifiNetwork:
        """Convert the access point to the public WiFi representation."""
        return WifiNetwork(
            ssid=self.ssid,
            signal=self.signal,
            authentication=self.authentication,
            connected=self.connected,
        )


def _decode_ssid(value: dbus.Array | dbus.ByteArray) -> str:
    """Decode a D-Bus byte array containing an SSID."""
    return bytes(value).decode("utf-8", errors="replace")


def _get_wifi_authentication(
    flags: int,
    wpa_flags: int,
    rsn_flags: int,
) -> WifiAuthentication:
    """Return the authentication method required by an access point."""
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
    access_point: _WifiAccessPoint,
) -> dbus.Dictionary:
    """Build NetworkManager settings for a new WiFi connection."""
    security_flags = access_point.wpa_flags | access_point.rsn_flags
    authentication = access_point.authentication

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


def _select_preferred_access_points(
    access_points: list[_WifiAccessPoint],
) -> dict[str, _WifiAccessPoint]:
    """Select the connected or strongest access point for each visible SSID."""
    preferred: dict[str, _WifiAccessPoint] = {}

    for candidate in access_points:
        if not candidate.ssid:
            continue

        current = preferred.get(candidate.ssid)
        if current is None:
            preferred[candidate.ssid] = candidate
            continue

        if current.connected:
            continue

        if candidate.connected or current.signal < candidate.signal:
            preferred[candidate.ssid] = candidate

    return preferred


class _NetworkManagerGateway:
    """Provide focused access to NetworkManager's WiFi D-Bus API.

    The gateway owns no global state. One instance represents one backend operation
    and reuses the supplied bus for all D-Bus calls made by that operation.

    Parameters
    ----------
    `bus` : `dbus.SystemBus`
        Connected D-Bus system bus.
    """

    def __init__(self, bus: dbus.SystemBus) -> None:
        self._bus = bus
        self._proxies: dict[str, object] = {}

    def _interface(self, path: str, interface_name: str) -> dbus.Interface:
        """Return a D-Bus interface for a NetworkManager object."""
        if path not in self._proxies:
            self._proxies[path] = self._bus.get_object(
                NETWORK_MANAGER_SERVICE,
                path,
            )

        proxy = self._proxies[path]
        return dbus.Interface(proxy, interface_name)

    def _properties(self, path: str) -> dbus.Interface:
        """Return the standard properties interface for an object."""
        return self._interface(path, dbus.PROPERTIES_IFACE)

    def _network_manager(self) -> dbus.Interface:
        """Return the main NetworkManager interface."""
        return self._interface(NETWORK_MANAGER_PATH, NETWORK_MANAGER_SERVICE)

    def _settings(self) -> dbus.Interface:
        """Return the NetworkManager settings interface."""
        return self._interface(
            NETWORK_MANAGER_SETTINGS_PATH,
            NETWORK_MANAGER_SETTINGS_INTERFACE,
        )

    def _get_wifi_device_paths(self) -> list[str]:
        """Return D-Bus object paths of all WiFi devices."""
        logger.debug("Query NetworkManager to find all WiFi device paths.")

        device_paths = self._network_manager().GetDevices()
        wifi_device_paths = []

        for device_path in device_paths:
            properties = self._properties(str(device_path))
            device_type = properties.Get(
                NETWORK_MANAGER_DEVICE_INTERFACE,
                "DeviceType",
            )

            if int(device_type) == NM_DEVICE_TYPE_WIFI:
                wifi_device_paths.append(str(device_path))

        return wifi_device_paths

    def _get_access_point(
        self,
        device_path: str,
        access_point_path: str,
        active_access_point_path: str,
    ) -> _WifiAccessPoint:
        """Return normalized data for one NetworkManager access point."""
        properties = self._properties(access_point_path).GetAll(
            NETWORK_MANAGER_ACCESS_POINT_INTERFACE
        )

        return _WifiAccessPoint(
            path=access_point_path,
            device_path=device_path,
            ssid=_decode_ssid(properties["Ssid"]),
            signal=int(properties["Strength"]),
            flags=int(properties["Flags"]),
            wpa_flags=int(properties["WpaFlags"]),
            rsn_flags=int(properties["RsnFlags"]),
            connected=access_point_path == active_access_point_path,
        )

    def _get_access_points(self) -> list[_WifiAccessPoint]:
        """Return normalized access points from every WiFi device."""
        access_points = []

        for device_path in self._get_wifi_device_paths():
            properties = self._properties(device_path)
            active_access_point_path = str(
                properties.Get(
                    NETWORK_MANAGER_WIRELESS_INTERFACE,
                    "ActiveAccessPoint",
                )
            )
            wireless = self._interface(
                device_path,
                NETWORK_MANAGER_WIRELESS_INTERFACE,
            )

            access_points.extend(
                self._get_access_point(
                    device_path,
                    str(access_point_path),
                    active_access_point_path,
                )
                for access_point_path in wireless.GetAllAccessPoints()
            )

        return access_points

    def _get_connection_target(self, ssid: str) -> _WifiAccessPoint:
        """Return the preferred visible access point for an SSID."""
        access_point = _select_preferred_access_points(
            self._get_access_points()
        ).get(ssid)

        if access_point is None:
            raise WifiError(f"WiFi network {ssid!r} was not found.")

        return access_point

    def _get_saved_profiles(self) -> list[SavedWifiProfile]:
        """Return all saved NetworkManager WiFi profiles."""
        profiles = []
        settings = self._settings()

        for connection_path in settings.ListConnections():
            connection = self._interface(
                str(connection_path),
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

    def _wait_for_wifi_connection(
        self,
        active_connection_path: str,
        timeout: float = 30.0,
    ) -> None:
        """Wait until a NetworkManager connection is activated."""
        properties = self._properties(active_connection_path)
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

    def wifi_is_enabled(self) -> bool:
        """Return whether WiFi is enabled."""
        logger.debug("Query NetworkManager for WiFi state via D-Bus.")
        enabled = self._properties(NETWORK_MANAGER_PATH).Get(
            NETWORK_MANAGER_SERVICE,
            "WirelessEnabled",
        )
        return bool(enabled)

    def list_visible_wifi_networks(self) -> list[WifiNetwork]:
        """Return visible WiFi networks."""
        logger.debug("Query NetworkManager to list all visible WiFi networks.")
        preferred = _select_preferred_access_points(self._get_access_points())
        return [access_point.to_network() for access_point in preferred.values()]

    def show_connected_wifi_network(self) -> WifiNetwork | None:
        """Return the first active WiFi network."""
        logger.debug("Query NetworkManager for the connected WiFi network.")

        for device_path in self._get_wifi_device_paths():
            active_access_point_path = str(
                self._properties(device_path).Get(
                    NETWORK_MANAGER_WIRELESS_INTERFACE,
                    "ActiveAccessPoint",
                )
            )
            if active_access_point_path == "/":
                continue

            access_point = self._get_access_point(
                device_path,
                active_access_point_path,
                active_access_point_path,
            )
            if access_point.ssid:
                return access_point.to_network()

        return None

    def list_saved_wifi_networks(self) -> list[SavedWifiProfile]:
        """Return all saved NetworkManager WiFi profiles."""
        logger.debug("Query saved WiFi profiles via D-Bus.")
        return self._get_saved_profiles()

    def enable_wifi(self, enable: bool) -> None:
        """Enable or disable WiFi."""
        logger.debug("Set NetworkManager WiFi state via D-Bus.")
        self._properties(NETWORK_MANAGER_PATH).Set(
            NETWORK_MANAGER_SERVICE,
            "WirelessEnabled",
            dbus.Boolean(enable),
        )

    def scan_wifi_networks(self) -> None:
        """Scan for visible WiFi networks."""
        logger.debug("Request a WiFi scan via D-Bus.")

        for device_path in self._get_wifi_device_paths():
            properties = self._properties(device_path)
            wireless = self._interface(
                device_path,
                NETWORK_MANAGER_WIRELESS_INTERFACE,
            )
            previous_last_scan = properties.Get(
                NETWORK_MANAGER_WIRELESS_INTERFACE,
                "LastScan",
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

    def connect_wifi_network(self, ssid: str, password: str | None) -> None:
        """Connect to a visible WiFi network."""
        logger.debug("Connect to WiFi network %r via D-Bus.", ssid)

        access_point = self._get_connection_target(ssid)
        saved_profile = next(
            (profile for profile in self._get_saved_profiles() if profile.ssid == ssid),
            None,
        )
        network_manager = self._network_manager()

        if saved_profile is not None:
            if password is not None:
                raise WifiError(
                    f"WiFi network {ssid!r} already has a saved profile; "
                    "connect without a password or forget the profile first."
                )

            connection_path = self._settings().GetConnectionByUuid(
                saved_profile.uuid
            )
            active_connection_path = network_manager.ActivateConnection(
                connection_path,
                access_point.device_path,
                access_point.path,
            )
            self._wait_for_wifi_connection(str(active_connection_path))
            return

        connection_settings = _build_wifi_connection_settings(
            ssid,
            password,
            access_point,
        )
        _, active_connection_path, _ = network_manager.AddAndActivateConnection2(
            connection_settings,
            access_point.device_path,
            access_point.path,
            dbus.Dictionary(
                {"persist": dbus.String("disk")},
                signature="sv",
            ),
        )
        self._wait_for_wifi_connection(str(active_connection_path))

    def disconnect_wifi_network(self) -> None:
        """Disconnect the active WiFi network."""
        logger.debug("Disconnect the active WiFi network via D-Bus.")

        for device_path in self._get_wifi_device_paths():
            active_connection = self._properties(device_path).Get(
                NETWORK_MANAGER_DEVICE_INTERFACE,
                "ActiveConnection",
            )
            if str(active_connection) == "/":
                continue

            self._interface(device_path, NETWORK_MANAGER_DEVICE_INTERFACE).Disconnect()
            return

        raise WifiError("No active WiFi connection was found.")

    def forget_wifi(self, uuid: str) -> None:
        """Delete a saved WiFi connection profile."""
        logger.debug("Delete WiFi connection profile %r via D-Bus.", uuid)
        connection_path = self._settings().GetConnectionByUuid(uuid)
        self._interface(
            str(connection_path),
            NETWORK_MANAGER_SETTINGS_CONNECTION_INTERFACE,
        ).Delete()
