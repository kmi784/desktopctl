from unittest.mock import Mock

import dbus
import pytest

from desktopctl.wifi import _network_manager as nm_backend
from desktopctl.wifi import nm_api

WIFI_DEVICE_PATH = "/org/freedesktop/NetworkManager/Devices/1"
ETHERNET_DEVICE_PATH = "/org/freedesktop/NetworkManager/Devices/2"
ACCESS_POINT_PATH = "/org/freedesktop/NetworkManager/AccessPoint/1"
ACTIVE_CONNECTION_PATH = "/org/freedesktop/NetworkManager/ActiveConnection/1"
SAVED_CONNECTION_PATH = "/org/freedesktop/NetworkManager/Settings/1"


@pytest.fixture
def fake_system_bus(system_bus_factory):
    return system_bus_factory(nm_api)


def _access_point(
    ssid: str,
    signal: int,
    *,
    flags: int = 0,
    wpa_flags: int = 0,
    rsn_flags: int = 0,
) -> dict[str, object]:
    """Return simulated NetworkManager access-point properties."""
    return {
        "Ssid": dbus.ByteArray(ssid.encode()),
        "Strength": dbus.Byte(signal),
        "Flags": dbus.UInt32(flags),
        "WpaFlags": dbus.UInt32(wpa_flags),
        "RsnFlags": dbus.UInt32(rsn_flags),
    }


def _access_point_model(
    ssid: str,
    signal: int,
    *,
    flags: int = 0,
    wpa_flags: int = 0,
    rsn_flags: int = 0,
    path: str = ACCESS_POINT_PATH,
    device_path: str = WIFI_DEVICE_PATH,
    connected: bool = False,
) -> nm_backend._WifiAccessPoint:
    """Return normalized NetworkManager access-point data for tests."""
    return nm_backend._WifiAccessPoint(
        path=path,
        device_path=device_path,
        ssid=ssid,
        signal=signal,
        flags=flags,
        wpa_flags=wpa_flags,
        rsn_flags=rsn_flags,
        connected=connected,
    )


def _configure_visible_wifi_dbus(
    monkeypatch: pytest.MonkeyPatch,
    fake_system_bus,
    access_points: dict[str, dict[str, object]],
    active_access_point: str = "/",
) -> None:
    """Configure a simulated NetworkManager D-Bus object tree."""
    manager_proxy = object()
    wifi_device_proxy = object()
    ethernet_device_proxy = object()
    access_point_proxies = {path: object() for path in access_points}

    fake_system_bus.proxies.update(
        {
            nm_api.NETWORK_MANAGER_PATH: manager_proxy,
            WIFI_DEVICE_PATH: wifi_device_proxy,
            ETHERNET_DEVICE_PATH: ethernet_device_proxy,
            **access_point_proxies,
        }
    )

    network_manager = Mock()
    network_manager.GetDevices.return_value = dbus.Array(
        [
            dbus.ObjectPath(WIFI_DEVICE_PATH),
            dbus.ObjectPath(ETHERNET_DEVICE_PATH),
        ],
        signature="o",
    )

    wifi_properties = Mock()

    def get_wifi_property(interface_name, property_name):
        if property_name == "DeviceType":
            assert interface_name == nm_api.NETWORK_MANAGER_DEVICE_INTERFACE
            return dbus.UInt32(2)

        assert interface_name == nm_api.NETWORK_MANAGER_WIRELESS_INTERFACE
        assert property_name == "ActiveAccessPoint"
        return dbus.ObjectPath(active_access_point)

    wifi_properties.Get.side_effect = get_wifi_property

    ethernet_properties = Mock()

    def get_ethernet_property(interface_name, property_name):
        assert interface_name == nm_api.NETWORK_MANAGER_DEVICE_INTERFACE
        assert property_name == "DeviceType"
        return dbus.UInt32(1)

    ethernet_properties.Get.side_effect = get_ethernet_property

    wireless = Mock()
    wireless.GetAllAccessPoints.return_value = dbus.Array(
        [dbus.ObjectPath(path) for path in access_points],
        signature="o",
    )

    interfaces = {
        (manager_proxy, nm_api.NETWORK_MANAGER_SERVICE): network_manager,
        (wifi_device_proxy, dbus.PROPERTIES_IFACE): wifi_properties,
        (
            wifi_device_proxy,
            nm_api.NETWORK_MANAGER_WIRELESS_INTERFACE,
        ): wireless,
        (ethernet_device_proxy, dbus.PROPERTIES_IFACE): ethernet_properties,
    }

    for path, properties in access_points.items():
        properties_interface = Mock()

        def get_all(interface_name, properties=properties):
            assert interface_name == nm_api.NETWORK_MANAGER_ACCESS_POINT_INTERFACE
            return properties

        properties_interface.GetAll.side_effect = get_all
        interfaces[(access_point_proxies[path], dbus.PROPERTIES_IFACE)] = (
            properties_interface
        )

    def fake_interface(proxy, interface_name):
        return interfaces[(proxy, interface_name)]

    monkeypatch.setattr(nm_api.dbus, "Interface", fake_interface)


@pytest.mark.parametrize(
    "enabled",
    [True, False],
    ids=["enabled", "disabled"],
)
def test_wifi_is_enabled(monkeypatch: pytest.MonkeyPatch, fake_system_bus, enabled):
    properties = Mock()
    properties.Get.return_value = dbus.Boolean(enabled)
    interface = Mock(return_value=properties)
    monkeypatch.setattr(nm_api.dbus, "Interface", interface)

    assert nm_api.wifi_is_enabled() is enabled
    assert fake_system_bus.get_object_calls == [
        (nm_api.NETWORK_MANAGER_SERVICE, nm_api.NETWORK_MANAGER_PATH)
    ]
    interface.assert_called_once_with(fake_system_bus.proxy, dbus.PROPERTIES_IFACE)
    properties.Get.assert_called_once_with(
        nm_api.NETWORK_MANAGER_SERVICE,
        "WirelessEnabled",
    )


def test_wifi_is_enabled_raises_dbus_exception(
    monkeypatch: pytest.MonkeyPatch, fake_system_bus
):
    properties = Mock()
    properties.Get.side_effect = dbus.exceptions.DBusException("NetworkManager failed")
    monkeypatch.setattr(nm_api.dbus, "Interface", Mock(return_value=properties))

    with pytest.raises(nm_api.WifiError, match="NetworkManager failed"):
        nm_api.wifi_is_enabled()


@pytest.mark.parametrize(
    ("flags", "wpa_flags", "rsn_flags", "expected"),
    [
        (0, 0, 0, "open"),
        (nm_api.NM_AP_FLAGS_PRIVACY, 0, 0, "password"),
        (0, nm_api.NM_AP_SEC_KEY_MGMT_PSK, 0, "password"),
        (0, 0, nm_api.NM_AP_SEC_KEY_MGMT_PSK, "password"),
        (0, 0, nm_api.NM_AP_SEC_KEY_MGMT_SAE, "password"),
        (0, 0, nm_api.NM_AP_SEC_KEY_MGMT_802_1X, "enterprise"),
        (0, 0, nm_api.NM_AP_SEC_KEY_MGMT_OWE, "open"),
        (0, 0, nm_api.NM_AP_SEC_KEY_MGMT_OWE_TM, "open"),
    ],
    ids=[
        "open",
        "wep",
        "wpa1-personal",
        "wpa2-personal",
        "wpa3-personal",
        "enterprise",
        "owe",
        "owe-transition",
    ],
)
def test_get_wifi_authentication(flags, wpa_flags, rsn_flags, expected):
    assert nm_api._get_wifi_authentication(flags, wpa_flags, rsn_flags) == expected


def test_list_visible_wifi_networks(monkeypatch: pytest.MonkeyPatch, fake_system_bus):
    access_point_1 = "/org/freedesktop/NetworkManager/AccessPoint/1"
    access_point_2 = "/org/freedesktop/NetworkManager/AccessPoint/2"
    access_point_3 = "/org/freedesktop/NetworkManager/AccessPoint/3"
    hidden_access_point = "/org/freedesktop/NetworkManager/AccessPoint/4"

    _configure_visible_wifi_dbus(
        monkeypatch,
        fake_system_bus,
        {
            access_point_1: _access_point(
                "Dummy:WiFi",
                12,
                flags=nm_api.NM_AP_FLAGS_PRIVACY,
                wpa_flags=nm_api.NM_AP_SEC_KEY_MGMT_PSK,
            ),
            access_point_2: _access_point(
                "Dummy",
                23,
                flags=nm_api.NM_AP_FLAGS_PRIVACY,
                rsn_flags=nm_api.NM_AP_SEC_KEY_MGMT_PSK,
            ),
            access_point_3: _access_point(
                "WiFi",
                34,
                flags=nm_api.NM_AP_FLAGS_PRIVACY,
                rsn_flags=nm_api.NM_AP_SEC_KEY_MGMT_SAE,
            ),
            hidden_access_point: _access_point("", 50),
        },
        active_access_point=access_point_2,
    )

    assert nm_api.list_visible_wifi_networks() == [
        nm_api.WifiNetwork("Dummy:WiFi", 12, "password", False),
        nm_api.WifiNetwork("Dummy", 23, "password", True),
        nm_api.WifiNetwork("WiFi", 34, "password", False),
    ]


@pytest.mark.parametrize(
    ("first_signal", "second_signal", "active_access_point", "expected"),
    [
        (
            12,
            23,
            "/",
            nm_api.WifiNetwork("Dummy", 23, "password", False),
        ),
        (
            12,
            23,
            "/org/freedesktop/NetworkManager/AccessPoint/1",
            nm_api.WifiNetwork("Dummy", 12, "password", True),
        ),
        (
            23,
            12,
            "/org/freedesktop/NetworkManager/AccessPoint/2",
            nm_api.WifiNetwork("Dummy", 12, "password", True),
        ),
    ],
    ids=[
        "prefer-greater-signal-strength",
        "prefer-connected-wifi-before",
        "prefer-connected-wifi-after",
    ],
)
def test_list_visible_wifi_networks_duplicated_ssid(
    monkeypatch: pytest.MonkeyPatch,
    fake_system_bus,
    first_signal,
    second_signal,
    active_access_point,
    expected,
):
    access_point_1 = "/org/freedesktop/NetworkManager/AccessPoint/1"
    access_point_2 = "/org/freedesktop/NetworkManager/AccessPoint/2"

    _configure_visible_wifi_dbus(
        monkeypatch,
        fake_system_bus,
        {
            access_point_1: _access_point(
                "Dummy",
                first_signal,
                rsn_flags=nm_api.NM_AP_SEC_KEY_MGMT_PSK,
            ),
            access_point_2: _access_point(
                "Dummy",
                second_signal,
                rsn_flags=nm_api.NM_AP_SEC_KEY_MGMT_PSK,
            ),
        },
        active_access_point=active_access_point,
    )

    assert nm_api.list_visible_wifi_networks() == [expected]


@pytest.mark.parametrize(
    ("first_connected", "expected_path"),
    [(False, "/access-point/strong"), (True, "/access-point/connected")],
    ids=["prefer-strongest", "prefer-connected"],
)
def test_get_connection_target_uses_listing_priority(
    monkeypatch: pytest.MonkeyPatch,
    first_connected: bool,
    expected_path: str,
):
    connected = _access_point_model(
        "WiFi",
        20,
        path="/access-point/connected",
        connected=first_connected,
    )
    strongest = _access_point_model(
        "WiFi",
        80,
        path="/access-point/strong",
    )
    gateway = nm_backend._NetworkManagerGateway(Mock())
    monkeypatch.setattr(
        gateway,
        "_get_access_points",
        Mock(return_value=[connected, strongest]),
    )

    assert gateway._get_connection_target("WiFi").path == expected_path


def test_list_visible_wifi_networks_raises_dbus_exception(
    monkeypatch: pytest.MonkeyPatch, fake_system_bus
):
    def fail_to_get_wifi_devices(_gateway):
        raise dbus.exceptions.DBusException("NetworkManager failed")

    monkeypatch.setattr(
        nm_backend._NetworkManagerGateway,
        "_get_wifi_device_paths",
        fail_to_get_wifi_devices,
    )

    with pytest.raises(nm_api.WifiError, match="NetworkManager failed"):
        nm_api.list_visible_wifi_networks()


def test_show_connected_wifi(monkeypatch: pytest.MonkeyPatch):
    connected_network = nm_api.WifiNetwork("WiFi", 67, "password", True)
    gateway = Mock()
    gateway.show_connected_wifi_network.return_value = connected_network
    monkeypatch.setattr(nm_api, "_gateway", Mock(return_value=gateway))

    assert nm_api.show_connected_wifi_network() == connected_network
    gateway.show_connected_wifi_network.assert_called_once_with()


def test_show_connected_wifi_returns_none(monkeypatch: pytest.MonkeyPatch):
    gateway = Mock()
    gateway.show_connected_wifi_network.return_value = None
    monkeypatch.setattr(nm_api, "_gateway", Mock(return_value=gateway))

    assert nm_api.show_connected_wifi_network() is None


def test_list_saved_wifi_networks(monkeypatch: pytest.MonkeyPatch, fake_system_bus):
    settings_path = "/org/freedesktop/NetworkManager/Settings"
    wifi_connection_path = "/org/freedesktop/NetworkManager/Settings/1"
    ethernet_connection_path = "/org/freedesktop/NetworkManager/Settings/2"

    settings = Mock()
    settings.ListConnections.return_value = dbus.Array(
        [
            dbus.ObjectPath(wifi_connection_path),
            dbus.ObjectPath(ethernet_connection_path),
        ],
        signature="o",
    )

    wifi_connection = Mock()
    wifi_connection.GetSettings.return_value = {
        "connection": {
            "id": dbus.String("Dummy:WiFi"),
            "uuid": dbus.String("123abc"),
            "type": dbus.String(nm_api.WIFI_IEEE),
        },
        nm_api.WIFI_IEEE: {
            "ssid": dbus.ByteArray(b"Dummy"),
        },
    }

    ethernet_connection = Mock()
    ethernet_connection.GetSettings.return_value = {
        "connection": {
            "id": dbus.String("Ethernet"),
            "uuid": dbus.String("456def"),
            "type": dbus.String("802-3-ethernet"),
        }
    }

    connections = iter([wifi_connection, ethernet_connection])

    def fake_interface(_proxy, interface_name):
        if interface_name == nm_api.NETWORK_MANAGER_SETTINGS_INTERFACE:
            return settings

        assert interface_name == nm_api.NETWORK_MANAGER_SETTINGS_CONNECTION_INTERFACE
        return next(connections)

    monkeypatch.setattr(nm_api.dbus, "Interface", fake_interface)

    assert nm_api.list_saved_wifi_networks() == [
        nm_api.SavedWifiProfile(
            uuid="123abc",
            profile_name="Dummy:WiFi",
            ssid="Dummy",
        )
    ]
    assert fake_system_bus.get_object_calls == [
        (nm_api.NETWORK_MANAGER_SERVICE, settings_path),
        (nm_api.NETWORK_MANAGER_SERVICE, dbus.ObjectPath(wifi_connection_path)),
        (nm_api.NETWORK_MANAGER_SERVICE, dbus.ObjectPath(ethernet_connection_path)),
    ]


def test_list_saved_wifi_networks_raises_dbus_exception(
    monkeypatch: pytest.MonkeyPatch, fake_system_bus
):
    settings = Mock()
    settings.ListConnections.side_effect = dbus.exceptions.DBusException(
        "NetworkManager failed"
    )

    monkeypatch.setattr(
        nm_api.dbus,
        "Interface",
        lambda _proxy, _interface_name: settings,
    )

    with pytest.raises(nm_api.WifiError, match="NetworkManager failed"):
        nm_api.list_saved_wifi_networks()


@pytest.mark.parametrize(
    "enable",
    [True, False],
    ids=["enable", "disable"],
)
def test_enable_wifi(monkeypatch: pytest.MonkeyPatch, fake_system_bus, enable):
    properties = Mock()
    interface = Mock(return_value=properties)
    monkeypatch.setattr(nm_api.dbus, "Interface", interface)

    nm_api.enable_wifi(enable)

    assert fake_system_bus.get_object_calls == [
        (nm_api.NETWORK_MANAGER_SERVICE, nm_api.NETWORK_MANAGER_PATH)
    ]
    interface.assert_called_once_with(fake_system_bus.proxy, dbus.PROPERTIES_IFACE)
    interface_name, property_name, property_value = properties.Set.call_args.args
    assert interface_name == nm_api.NETWORK_MANAGER_SERVICE
    assert property_name == "WirelessEnabled"
    assert type(property_value) is dbus.Boolean
    assert bool(property_value) is enable


def test_enable_wifi_raises_dbus_exception(
    monkeypatch: pytest.MonkeyPatch, fake_system_bus
):
    properties = Mock()
    properties.Set.side_effect = dbus.exceptions.DBusException("NetworkManager failed")
    monkeypatch.setattr(nm_api.dbus, "Interface", Mock(return_value=properties))

    with pytest.raises(nm_api.WifiError, match="NetworkManager failed"):
        nm_api.enable_wifi(True)


def _configure_wifi_scan_dbus(monkeypatch, fake_system_bus):
    """Configure simulated D-Bus interfaces for a WiFi scan."""
    properties = Mock()
    wireless = Mock()

    def fake_interface(proxy, interface_name):
        assert proxy is fake_system_bus.proxy
        if interface_name == dbus.PROPERTIES_IFACE:
            return properties

        assert interface_name == nm_api.NETWORK_MANAGER_WIRELESS_INTERFACE
        return wireless

    monkeypatch.setattr(
        nm_backend._NetworkManagerGateway,
        "_get_wifi_device_paths",
        lambda _gateway: [WIFI_DEVICE_PATH],
    )
    monkeypatch.setattr(nm_api.dbus, "Interface", fake_interface)

    return properties, wireless


def test_scan_wifi_networks(monkeypatch: pytest.MonkeyPatch, fake_system_bus):
    properties, wireless = _configure_wifi_scan_dbus(monkeypatch, fake_system_bus)
    properties.Get.side_effect = [100, 100, 101]
    sleep = Mock()
    monkeypatch.setattr(nm_backend, "monotonic", Mock(return_value=0.0))
    monkeypatch.setattr(nm_backend, "sleep", sleep)

    nm_api.scan_wifi_networks()

    assert fake_system_bus.get_object_calls == [
        (nm_api.NETWORK_MANAGER_SERVICE, WIFI_DEVICE_PATH)
    ]
    properties.Get.assert_called_with(
        nm_api.NETWORK_MANAGER_WIRELESS_INTERFACE, "LastScan"
    )
    assert properties.Get.call_count == 3
    options = wireless.RequestScan.call_args.args[0]
    assert type(options) is dbus.Dictionary
    assert options.signature == "sv"
    assert not options
    sleep.assert_called_once_with(0.2)


def test_scan_wifi_networks_without_device(
    monkeypatch: pytest.MonkeyPatch, fake_system_bus
):
    monkeypatch.setattr(
        nm_backend._NetworkManagerGateway,
        "_get_wifi_device_paths",
        lambda _gateway: [],
    )

    nm_api.scan_wifi_networks()

    assert not fake_system_bus.get_object_calls


def test_scan_wifi_networks_raises_dbus_exception(
    monkeypatch: pytest.MonkeyPatch, fake_system_bus
):
    properties, wireless = _configure_wifi_scan_dbus(monkeypatch, fake_system_bus)
    properties.Get.return_value = 100
    wireless.RequestScan.side_effect = dbus.exceptions.DBusException(
        "NetworkManager failed"
    )

    with pytest.raises(nm_api.WifiError, match="NetworkManager failed"):
        nm_api.scan_wifi_networks()


def test_scan_wifi_networks_raises_timeout(
    monkeypatch: pytest.MonkeyPatch, fake_system_bus
):
    properties, _wireless = _configure_wifi_scan_dbus(monkeypatch, fake_system_bus)
    properties.Get.return_value = 100
    sleep = Mock()
    monkeypatch.setattr(nm_backend, "monotonic", Mock(side_effect=[0.0, 10.0]))
    monkeypatch.setattr(nm_backend, "sleep", sleep)

    with pytest.raises(nm_api.WifiError, match="WiFi scan timed out"):
        nm_api.scan_wifi_networks()

    sleep.assert_not_called()


@pytest.fixture
def wifi_connect_dbus(monkeypatch, fake_system_bus):
    """Configure simulated D-Bus interfaces for a WiFi connection."""
    network_manager = Mock()
    settings = Mock()
    wait_for_connection = Mock()
    profiles = []
    access_point = _access_point_model("WiFi", 50)

    monkeypatch.setattr(
        nm_backend._NetworkManagerGateway,
        "_get_connection_target",
        lambda _gateway, _ssid: access_point,
    )
    monkeypatch.setattr(
        nm_backend._NetworkManagerGateway,
        "_get_saved_profiles",
        lambda _gateway: profiles,
    )
    monkeypatch.setattr(
        nm_backend._NetworkManagerGateway,
        "_wait_for_wifi_connection",
        lambda _gateway, path: wait_for_connection(path),
    )

    def fake_interface(_proxy, interface_name):
        if interface_name == nm_api.NETWORK_MANAGER_SERVICE:
            return network_manager

        assert interface_name == nm_api.NETWORK_MANAGER_SETTINGS_INTERFACE
        return settings

    monkeypatch.setattr(nm_api.dbus, "Interface", fake_interface)
    settings.GetConnectionByUuid.return_value = dbus.ObjectPath(SAVED_CONNECTION_PATH)
    network_manager.ActivateConnection.return_value = dbus.ObjectPath(
        ACTIVE_CONNECTION_PATH
    )
    network_manager.AddAndActivateConnection2.return_value = (
        dbus.ObjectPath(SAVED_CONNECTION_PATH),
        dbus.ObjectPath(ACTIVE_CONNECTION_PATH),
        dbus.Dictionary({}, signature="sv"),
    )

    return network_manager, settings, wait_for_connection, profiles


def test_connect_saved_wifi_network(fake_system_bus, wifi_connect_dbus):
    network_manager, settings, wait_for_connection, profiles = wifi_connect_dbus
    profiles.append(nm_api.SavedWifiProfile("123abc", "WiFi profile", "WiFi"))

    nm_api.connect_wifi_network("WiFi")

    settings.GetConnectionByUuid.assert_called_once_with("123abc")
    network_manager.ActivateConnection.assert_called_once_with(
        dbus.ObjectPath(SAVED_CONNECTION_PATH),
        WIFI_DEVICE_PATH,
        ACCESS_POINT_PATH,
    )
    wait_for_connection.assert_called_once_with(ACTIVE_CONNECTION_PATH)
    assert len(fake_system_bus.system_bus_calls) == 1


def test_connect_new_wifi_network(
    monkeypatch,
    fake_system_bus,
    wifi_connect_dbus,
):
    network_manager, _settings, wait_for_connection, _profiles = wifi_connect_dbus
    connection_settings = dbus.Dictionary({}, signature="sa{sv}")
    build_settings = Mock(return_value=connection_settings)
    monkeypatch.setattr(
        nm_backend,
        "_build_wifi_connection_settings",
        build_settings,
    )

    nm_api.connect_wifi_network("WiFi", "password123")

    build_settings.assert_called_once()
    connection, device, access_point, options = (
        network_manager.AddAndActivateConnection2.call_args.args
    )
    assert connection is connection_settings
    assert (device, access_point) == (WIFI_DEVICE_PATH, ACCESS_POINT_PATH)
    assert str(options["persist"]) == "disk"
    wait_for_connection.assert_called_once_with(ACTIVE_CONNECTION_PATH)
    assert len(fake_system_bus.system_bus_calls) == 1


@pytest.mark.parametrize(
    ("rsn_flags", "password", "key_management"),
    [
        (0, None, None),
        (nm_api.NM_AP_SEC_KEY_MGMT_PSK, "password123", "wpa-psk"),
        (nm_api.NM_AP_SEC_KEY_MGMT_SAE, "password123", "sae"),
        (nm_api.NM_AP_SEC_KEY_MGMT_OWE, None, "owe"),
    ],
    ids=["open", "wpa2", "wpa3", "owe"],
)
def test_build_wifi_connection_settings(rsn_flags, password, key_management):
    settings = nm_backend._build_wifi_connection_settings(
        "WiFi",
        password,
        _access_point_model("WiFi", 50, rsn_flags=rsn_flags),
    )

    assert settings.signature == "sa{sv}"
    assert str(settings["connection"]["id"]) == "WiFi"
    assert bytes(settings[nm_api.WIFI_IEEE]["ssid"]) == b"WiFi"
    security = settings.get(nm_api.WIFI_SECURITY)
    actual_key_management = None if security is None else str(security["key-mgmt"])
    assert actual_key_management == key_management
    if password is not None:
        assert str(security["psk"]) == password


@pytest.mark.parametrize(
    ("properties", "password", "message"),
    [
        (
            _access_point("WiFi", 50, rsn_flags=nm_api.NM_AP_SEC_KEY_MGMT_PSK),
            None,
            "requires a password",
        ),
        (
            _access_point("WiFi", 50, rsn_flags=nm_api.NM_AP_SEC_KEY_MGMT_802_1X),
            None,
            "enterprise WiFi network is not supported",
        ),
        (_access_point("WiFi", 50), "password123", "does not require a password"),
        (
            _access_point("WiFi", 50, flags=nm_api.NM_AP_FLAGS_PRIVACY),
            "password123",
            "WEP WiFi network is not supported",
        ),
    ],
    ids=["missing-password", "enterprise", "open-with-password", "wep"],
)
def test_connect_new_wifi_network_rejects_unsupported_input(
    properties,
    password,
    message,
):
    with pytest.raises(nm_api.WifiError, match=message):
        nm_backend._build_wifi_connection_settings(
            "WiFi",
            password,
            _access_point_model(
                "WiFi",
                50,
                flags=int(properties["Flags"]),
                wpa_flags=int(properties["WpaFlags"]),
                rsn_flags=int(properties["RsnFlags"]),
            ),
        )


def test_connect_saved_wifi_network_rejects_password(wifi_connect_dbus):
    _manager, _settings, _wait, profiles = wifi_connect_dbus
    profiles.append(nm_api.SavedWifiProfile("123abc", "WiFi profile", "WiFi"))

    with pytest.raises(nm_api.WifiError, match="already has a saved profile"):
        nm_api.connect_wifi_network("WiFi", "password123")


def test_connect_wifi_network_raises_error_when_not_visible(
    monkeypatch, wifi_connect_dbus
):
    def fail_to_find_target(_gateway, ssid):
        raise nm_api.WifiError(f"WiFi network {ssid!r} was not found.")

    monkeypatch.setattr(
        nm_backend._NetworkManagerGateway,
        "_get_connection_target",
        fail_to_find_target,
    )

    with pytest.raises(nm_api.WifiError, match="was not found"):
        nm_api.connect_wifi_network("WiFi")


def test_connect_wifi_network_raises_dbus_exception(wifi_connect_dbus):
    network_manager, _settings, _wait, _state = wifi_connect_dbus
    network_manager.AddAndActivateConnection2.side_effect = (
        dbus.exceptions.DBusException("NetworkManager failed")
    )

    with pytest.raises(nm_api.WifiError, match="NetworkManager failed"):
        nm_api.connect_wifi_network("WiFi")


def test_wait_for_wifi_connection(monkeypatch, fake_system_bus):
    properties = Mock()
    properties.Get.side_effect = [1, nm_api.NM_ACTIVE_CONNECTION_STATE_ACTIVATED]
    sleep = Mock()
    monkeypatch.setattr(nm_api.dbus, "Interface", Mock(return_value=properties))
    monkeypatch.setattr(nm_backend, "monotonic", Mock(return_value=0.0))
    monkeypatch.setattr(nm_backend, "sleep", sleep)

    nm_backend._NetworkManagerGateway(fake_system_bus)._wait_for_wifi_connection(
        ACTIVE_CONNECTION_PATH
    )

    sleep.assert_called_once_with(0.2)
    properties.Get.assert_called_with(
        nm_api.NETWORK_MANAGER_ACTIVE_CONNECTION_INTERFACE,
        "State",
    )


@pytest.mark.parametrize(
    ("state", "message"),
    [
        (nm_api.NM_ACTIVE_CONNECTION_STATE_DEACTIVATED, "connection failed"),
        (1, "connection timed out"),
    ],
    ids=["failed", "timeout"],
)
def test_wait_for_wifi_connection_raises_error(
    fake_system_bus,
    monkeypatch,
    state,
    message,
):
    properties = Mock()
    properties.Get.return_value = state
    monkeypatch.setattr(nm_api.dbus, "Interface", Mock(return_value=properties))
    monkeypatch.setattr(nm_backend, "monotonic", Mock(side_effect=[0.0, 30.0]))
    sleep = Mock()
    monkeypatch.setattr(nm_backend, "sleep", sleep)

    with pytest.raises(nm_api.WifiError, match=message):
        nm_backend._NetworkManagerGateway(fake_system_bus)._wait_for_wifi_connection(
            ACTIVE_CONNECTION_PATH
        )

    sleep.assert_not_called()


def test_disconnect_wifi_network(monkeypatch, fake_system_bus):
    properties = Mock()
    properties.Get.return_value = dbus.ObjectPath(ACTIVE_CONNECTION_PATH)
    device = Mock()
    monkeypatch.setattr(
        nm_backend._NetworkManagerGateway,
        "_get_wifi_device_paths",
        lambda _gateway: [WIFI_DEVICE_PATH],
    )

    def fake_interface(_proxy, interface_name):
        if interface_name == dbus.PROPERTIES_IFACE:
            return properties
        assert interface_name == nm_api.NETWORK_MANAGER_DEVICE_INTERFACE
        return device

    monkeypatch.setattr(nm_api.dbus, "Interface", fake_interface)

    nm_api.disconnect_wifi_network()

    properties.Get.assert_called_once_with(
        nm_api.NETWORK_MANAGER_DEVICE_INTERFACE,
        "ActiveConnection",
    )
    device.Disconnect.assert_called_once_with()


def test_disconnect_wifi_network_raises_error_when_not_connected(
    monkeypatch,
    fake_system_bus,
):
    properties = Mock()
    properties.Get.return_value = dbus.ObjectPath("/")
    monkeypatch.setattr(
        nm_backend._NetworkManagerGateway,
        "_get_wifi_device_paths",
        lambda _gateway: [WIFI_DEVICE_PATH],
    )
    monkeypatch.setattr(
        nm_api.dbus,
        "Interface",
        Mock(return_value=properties),
    )

    with pytest.raises(nm_api.WifiError, match="active WiFi connection"):
        nm_api.disconnect_wifi_network()


def test_disconnect_wifi_network_raises_dbus_exception(
    monkeypatch,
    fake_system_bus,
):
    properties = Mock()
    properties.Get.return_value = dbus.ObjectPath(ACTIVE_CONNECTION_PATH)
    device = Mock()
    device.Disconnect.side_effect = dbus.exceptions.DBusException("Disconnect failed")
    monkeypatch.setattr(
        nm_backend._NetworkManagerGateway,
        "_get_wifi_device_paths",
        lambda _gateway: [WIFI_DEVICE_PATH],
    )
    monkeypatch.setattr(
        nm_api.dbus,
        "Interface",
        Mock(side_effect=[properties, device]),
    )

    with pytest.raises(nm_api.WifiError, match="Disconnect failed"):
        nm_api.disconnect_wifi_network()


def test_forget_wifi(monkeypatch, fake_system_bus):
    settings = Mock()
    settings.GetConnectionByUuid.return_value = dbus.ObjectPath(SAVED_CONNECTION_PATH)
    connection = Mock()
    monkeypatch.setattr(
        nm_api.dbus,
        "Interface",
        Mock(side_effect=[settings, connection]),
    )

    nm_api.forget_wifi("123abc")

    settings.GetConnectionByUuid.assert_called_once_with("123abc")
    connection.Delete.assert_called_once_with()


def test_forget_wifi_raises_dbus_exception(monkeypatch, fake_system_bus):
    settings = Mock()
    settings.GetConnectionByUuid.return_value = dbus.ObjectPath(SAVED_CONNECTION_PATH)
    connection = Mock()
    connection.Delete.side_effect = dbus.exceptions.DBusException("Delete failed")
    monkeypatch.setattr(
        nm_api.dbus,
        "Interface",
        Mock(side_effect=[settings, connection]),
    )

    with pytest.raises(nm_api.WifiError, match="Delete failed"):
        nm_api.forget_wifi("123abc")
