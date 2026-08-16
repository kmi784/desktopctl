import dbus

from ..misc import translate_dbus_errors
from ._network_manager import (
    NETWORK_MANAGER_ACCESS_POINT_INTERFACE,
    NETWORK_MANAGER_ACTIVE_CONNECTION_INTERFACE,
    NETWORK_MANAGER_DEVICE_INTERFACE,
    NETWORK_MANAGER_PATH,
    NETWORK_MANAGER_SERVICE,
    NETWORK_MANAGER_SETTINGS_CONNECTION_INTERFACE,
    NETWORK_MANAGER_SETTINGS_INTERFACE,
    NETWORK_MANAGER_SETTINGS_PATH,
    NETWORK_MANAGER_WIRELESS_INTERFACE,
    NM_ACTIVE_CONNECTION_STATE_ACTIVATED,
    NM_ACTIVE_CONNECTION_STATE_DEACTIVATED,
    NM_ACTIVE_CONNECTION_STATE_DEACTIVATING,
    NM_AP_FLAGS_PRIVACY,
    NM_AP_SEC_KEY_MGMT_802_1X,
    NM_AP_SEC_KEY_MGMT_EAP_SUITE_B_192,
    NM_AP_SEC_KEY_MGMT_OWE,
    NM_AP_SEC_KEY_MGMT_OWE_TM,
    NM_AP_SEC_KEY_MGMT_PSK,
    NM_AP_SEC_KEY_MGMT_SAE,
    WIFI_IEEE,
    WIFI_SECURITY,
    SavedWifiProfile,
    WifiAuthentication,
    WifiError,
    WifiNetwork,
    _build_wifi_connection_settings,
    _get_wifi_authentication,
    _NetworkManagerGateway,
)

__all__ = [
    "NETWORK_MANAGER_ACCESS_POINT_INTERFACE",
    "NETWORK_MANAGER_ACTIVE_CONNECTION_INTERFACE",
    "NETWORK_MANAGER_DEVICE_INTERFACE",
    "NETWORK_MANAGER_PATH",
    "NETWORK_MANAGER_SERVICE",
    "NETWORK_MANAGER_SETTINGS_CONNECTION_INTERFACE",
    "NETWORK_MANAGER_SETTINGS_INTERFACE",
    "NETWORK_MANAGER_SETTINGS_PATH",
    "NETWORK_MANAGER_WIRELESS_INTERFACE",
    "NM_ACTIVE_CONNECTION_STATE_ACTIVATED",
    "NM_ACTIVE_CONNECTION_STATE_DEACTIVATED",
    "NM_ACTIVE_CONNECTION_STATE_DEACTIVATING",
    "NM_AP_FLAGS_PRIVACY",
    "NM_AP_SEC_KEY_MGMT_802_1X",
    "NM_AP_SEC_KEY_MGMT_EAP_SUITE_B_192",
    "NM_AP_SEC_KEY_MGMT_OWE",
    "NM_AP_SEC_KEY_MGMT_OWE_TM",
    "NM_AP_SEC_KEY_MGMT_PSK",
    "NM_AP_SEC_KEY_MGMT_SAE",
    "WIFI_IEEE",
    "WIFI_SECURITY",
    "SavedWifiProfile",
    "WifiAuthentication",
    "WifiError",
    "WifiNetwork",
    "_build_wifi_connection_settings",
    "_get_wifi_authentication",
    "connect_wifi_network",
    "disconnect_wifi_network",
    "enable_wifi",
    "forget_wifi",
    "list_saved_wifi_networks",
    "list_visible_wifi_networks",
    "scan_wifi_networks",
    "show_connected_wifi_network",
    "wifi_is_enabled",
]


def _gateway() -> _NetworkManagerGateway:
    """Return a NetworkManager gateway connected to the system bus."""
    return _NetworkManagerGateway(dbus.SystemBus())


@translate_dbus_errors(WifiError)
def wifi_is_enabled() -> bool:
    """Return whether WiFi is enabled.

    Returns
    -------
    `bool`
        `True` if WiFi is enabled; otherwise, `False`.
    """
    return _gateway().wifi_is_enabled()


@translate_dbus_errors(WifiError)
def list_visible_wifi_networks() -> list[WifiNetwork]:
    """List all visible WiFi networks.

    Returns
    -------
    `list[WifiNetwork]`
        Visible WiFi networks reported by NetworkManager.
    """
    return _gateway().list_visible_wifi_networks()


@translate_dbus_errors(WifiError)
def show_connected_wifi_network() -> WifiNetwork | None:
    """Return the currently connected WiFi network.

    Returns
    -------
    `WifiNetwork` or `None`
        Connected WiFi network, or `None` if no network is connected.
    """
    return _gateway().show_connected_wifi_network()


@translate_dbus_errors(WifiError)
def list_saved_wifi_networks() -> list[SavedWifiProfile]:
    """List saved NetworkManager WiFi profiles."""
    return _gateway().list_saved_wifi_networks()


@translate_dbus_errors(WifiError)
def enable_wifi(enable: bool) -> None:
    """Enable or disable WiFi.

    Parameters
    ----------
    `enable` : `bool`
        Whether to enable (`True`) or disable (`False`) WiFi.
    """
    _gateway().enable_wifi(enable)


@translate_dbus_errors(WifiError)
def scan_wifi_networks() -> None:
    """Scan for visible WiFi networks."""
    _gateway().scan_wifi_networks()


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
    _gateway().connect_wifi_network(ssid, password)


@translate_dbus_errors(WifiError)
def disconnect_wifi_network() -> None:
    """Disconnect the active WiFi network."""
    _gateway().disconnect_wifi_network()


@translate_dbus_errors(WifiError)
def forget_wifi(uuid: str) -> None:
    """Delete a saved WiFi connection profile.

    Parameters
    ----------
    `uuid` : `str`
        Unique identifier of the NetworkManager connection profile.
    """
    _gateway().forget_wifi(uuid)
