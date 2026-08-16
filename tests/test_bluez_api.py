from unittest.mock import Mock

import dbus
import pytest

from desktopctl.bluetooth import bluez_api

BLUEZ_ROOT_PATH = "/"
BLUETOOTH_DEVICE_PATH = "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"


@pytest.fixture
def fake_system_bus(system_bus_factory):
    return system_bus_factory(bluez_api)


@pytest.fixture
def bluetooth_devices() -> list[bluez_api.BluetoothDevice]:
    return [
        _bluetooth_device("00:11:22:33:44:55", connected=True),
        _bluetooth_device("11:22:33:44:55:66", paired=True),
        _bluetooth_device("22:33:44:55:66:77", paired=True, connected=True),
        _bluetooth_device("33:44:55:66:77:88"),
    ]


def _bluetooth_device(
    address: str,
    *,
    name: str | None = None,
    rssi: int | None = None,
    battery: int | None = None,
    paired: bool = False,
    connected: bool = False,
) -> bluez_api.BluetoothDevice:
    """Return a Bluetooth device for tests."""
    return bluez_api.BluetoothDevice(
        address=address,
        name=name,
        rssi=rssi,
        battery=battery,
        paired=paired,
        connected=connected,
    )


@pytest.mark.parametrize(
    "enabled",
    [True, False],
    ids=["enabled", "disabled"],
)
def test_bluetooth_is_enabled(monkeypatch, fake_system_bus, enabled):
    properties = Mock()
    properties.Get.return_value = dbus.Boolean(enabled)
    interface = Mock(return_value=properties)
    monkeypatch.setattr(bluez_api.dbus, "Interface", interface)

    assert bluez_api.bluetooth_is_enabled() is enabled
    assert fake_system_bus.get_object_calls == [
        (bluez_api.BLUEZ_SERVICE, bluez_api.ADAPTER_PATH)
    ]
    interface.assert_called_once_with(fake_system_bus.proxy, dbus.PROPERTIES_IFACE)
    properties.Get.assert_called_once_with(
        bluez_api.BLUEZ_ADAPTER_INTERFACE,
        "Powered",
    )


def test_bluetooth_is_enabled_raises_dbus_exception(
    monkeypatch: pytest.MonkeyPatch, fake_system_bus
):
    properties = Mock()
    properties.Get.side_effect = dbus.exceptions.DBusException("BlueZ failed")
    monkeypatch.setattr(bluez_api.dbus, "Interface", Mock(return_value=properties))

    with pytest.raises(bluez_api.BluetoothError, match="BlueZ failed"):
        bluez_api.bluetooth_is_enabled()


def test_list_visible_bluetooth_devices(
    monkeypatch: pytest.MonkeyPatch, fake_system_bus
):
    bluez_proxy = object()
    fake_system_bus.proxies[BLUEZ_ROOT_PATH] = bluez_proxy

    object_manager = Mock()
    object_manager.GetManagedObjects.return_value = {
        bluez_api.ADAPTER_PATH: {
            bluez_api.BLUEZ_ADAPTER_INTERFACE: {
                "Address": dbus.String("00:11:22:33:44:55"),
            }
        },
        "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF": {
            bluez_api.BLUEZ_DEVICE_INTERFACE: {
                "Address": dbus.String("AA:BB:CC:DD:EE:FF"),
                "Alias": dbus.String("Headphones"),
                "Name": dbus.String("Raw device name"),
                "RSSI": dbus.Int16(-42),
                "Paired": dbus.Boolean(True),
                "Connected": dbus.Boolean(True),
            },
            "org.bluez.Battery1": {
                "Percentage": dbus.Byte(73),
            },
        },
        "/org/bluez/hci0/dev_11_22_33_44_55_66": {
            bluez_api.BLUEZ_DEVICE_INTERFACE: {
                "Address": dbus.String("11:22:33:44:55:66"),
                "Name": dbus.String("Keyboard"),
                "Paired": dbus.Boolean(False),
                "Connected": dbus.Boolean(False),
            }
        },
        "/org/bluez/hci0/dev_22_33_44_55_66_77": {
            bluez_api.BLUEZ_DEVICE_INTERFACE: {
                "Address": dbus.String("22:33:44:55:66:77"),
                "Paired": dbus.Boolean(False),
                "Connected": dbus.Boolean(False),
            },
            "org.bluez.Battery1": {},
        },
    }

    def fake_interface(proxy, interface_name):
        assert proxy is bluez_proxy
        assert interface_name == "org.freedesktop.DBus.ObjectManager"
        return object_manager

    monkeypatch.setattr(bluez_api.dbus, "Interface", fake_interface)

    assert bluez_api.list_visible_bluetooth_devices() == [
        _bluetooth_device(
            "AA:BB:CC:DD:EE:FF",
            name="Headphones",
            rssi=-42,
            battery=73,
            paired=True,
            connected=True,
        ),
        _bluetooth_device(
            "11:22:33:44:55:66",
            name="Keyboard",
        ),
        _bluetooth_device("22:33:44:55:66:77"),
    ]
    assert fake_system_bus.get_object_calls == [
        (bluez_api.BLUEZ_SERVICE, BLUEZ_ROOT_PATH)
    ]


def test_list_visible_bluetooth_devices_raises_dbus_exception(
    monkeypatch: pytest.MonkeyPatch, fake_system_bus
):
    object_manager = Mock()
    object_manager.GetManagedObjects.side_effect = dbus.exceptions.DBusException(
        "BlueZ failed"
    )

    monkeypatch.setattr(
        bluez_api.dbus,
        "Interface",
        lambda _proxy, _interface_name: object_manager,
    )

    with pytest.raises(bluez_api.BluetoothError, match="BlueZ failed"):
        bluez_api.list_visible_bluetooth_devices()


def test_list_connected_bluetooth_devices(
    monkeypatch: pytest.MonkeyPatch,
    bluetooth_devices: list[bluez_api.BluetoothDevice],
):
    monkeypatch.setattr(
        bluez_api,
        "list_visible_bluetooth_devices",
        lambda: bluetooth_devices,
    )

    assert bluez_api.list_connected_bluetooth_devices() == [
        bluetooth_devices[0],
        bluetooth_devices[2],
    ]


def test_list_paired_bluetooth_devices(
    monkeypatch: pytest.MonkeyPatch,
    bluetooth_devices: list[bluez_api.BluetoothDevice],
):
    monkeypatch.setattr(
        bluez_api,
        "list_visible_bluetooth_devices",
        lambda: bluetooth_devices,
    )

    assert bluez_api.list_paired_bluetooth_devices() == [
        bluetooth_devices[1],
        bluetooth_devices[2],
    ]


@pytest.mark.parametrize(
    "enable",
    [True, False],
    ids=["enable", "disable"],
)
def test_enable_bluetooth(monkeypatch: pytest.MonkeyPatch, fake_system_bus, enable):
    properties = Mock()
    interface = Mock(return_value=properties)
    monkeypatch.setattr(bluez_api.dbus, "Interface", interface)

    bluez_api.enable_bluetooth(enable)

    assert fake_system_bus.get_object_calls == [
        (bluez_api.BLUEZ_SERVICE, bluez_api.ADAPTER_PATH)
    ]
    interface.assert_called_once_with(fake_system_bus.proxy, dbus.PROPERTIES_IFACE)
    interface_name, property_name, property_value = properties.Set.call_args.args
    assert interface_name == bluez_api.BLUEZ_ADAPTER_INTERFACE
    assert property_name == "Powered"
    assert type(property_value) is dbus.Boolean
    assert bool(property_value) is enable


def test_enable_bluetooth_raises_dbus_exception(
    monkeypatch: pytest.MonkeyPatch, fake_system_bus
):
    properties = Mock()
    properties.Set.side_effect = dbus.exceptions.DBusException("BlueZ failed")
    monkeypatch.setattr(bluez_api.dbus, "Interface", Mock(return_value=properties))

    with pytest.raises(bluez_api.BluetoothError, match="BlueZ failed"):
        bluez_api.enable_bluetooth(True)


def test_scan_bluetooth_devices(monkeypatch: pytest.MonkeyPatch, fake_system_bus):
    adapter = Mock()
    interface = Mock(return_value=adapter)
    sleep = Mock()
    monkeypatch.setattr(bluez_api.dbus, "Interface", interface)
    monkeypatch.setattr(bluez_api, "sleep", sleep)

    bluez_api.scan_bluetooth_devices(duration=3)

    assert fake_system_bus.get_object_calls == [
        (bluez_api.BLUEZ_SERVICE, bluez_api.ADAPTER_PATH)
    ]
    interface.assert_called_once_with(
        fake_system_bus.proxy,
        bluez_api.BLUEZ_ADAPTER_INTERFACE,
    )
    adapter.StartDiscovery.assert_called_once_with()
    sleep.assert_called_once_with(3)
    adapter.StopDiscovery.assert_called_once_with()


def test_scan_bluetooth_devices_stops_discovery_after_error(
    monkeypatch: pytest.MonkeyPatch, fake_system_bus
):
    adapter = Mock()
    monkeypatch.setattr(bluez_api.dbus, "Interface", Mock(return_value=adapter))
    monkeypatch.setattr(
        bluez_api,
        "sleep",
        Mock(side_effect=RuntimeError("Scan interrupted")),
    )

    with pytest.raises(RuntimeError, match="Scan interrupted"):
        bluez_api.scan_bluetooth_devices()

    adapter.StopDiscovery.assert_called_once_with()


def test_scan_bluetooth_devices_raises_dbus_exception(
    monkeypatch: pytest.MonkeyPatch, fake_system_bus
):
    adapter = Mock()
    adapter.StartDiscovery.side_effect = dbus.exceptions.DBusException("BlueZ failed")
    monkeypatch.setattr(bluez_api.dbus, "Interface", Mock(return_value=adapter))

    with pytest.raises(bluez_api.BluetoothError, match="BlueZ failed"):
        bluez_api.scan_bluetooth_devices()

    adapter.StopDiscovery.assert_not_called()


def test_pair_bluetooth_device(monkeypatch, fake_system_bus):
    bluez_proxy = object()
    device_proxy = object()
    fake_system_bus.proxies.update(
        {
            BLUEZ_ROOT_PATH: bluez_proxy,
            BLUETOOTH_DEVICE_PATH: device_proxy,
        }
    )
    object_manager = Mock()
    object_manager.GetManagedObjects.return_value = {
        BLUETOOTH_DEVICE_PATH: {
            bluez_api.BLUEZ_DEVICE_INTERFACE: {
                "Address": dbus.String("AA:BB:CC:DD:EE:FF"),
            }
        }
    }
    device = Mock()

    def fake_interface(proxy, interface_name):
        if proxy is bluez_proxy:
            assert interface_name == bluez_api.DBUS_OBJECT_MANAGER_INTERFACE
            return object_manager

        assert proxy is device_proxy
        assert interface_name == bluez_api.BLUEZ_DEVICE_INTERFACE
        return device

    monkeypatch.setattr(bluez_api.dbus, "Interface", fake_interface)

    bluez_api.pair_bluetooth_device("aa:bb:cc:dd:ee:ff")

    device.Pair.assert_called_once_with()
    assert fake_system_bus.get_object_calls == [
        (bluez_api.BLUEZ_SERVICE, BLUEZ_ROOT_PATH),
        (bluez_api.BLUEZ_SERVICE, BLUETOOTH_DEVICE_PATH),
    ]


def test_pair_bluetooth_device_raises_error_when_not_discovered(
    monkeypatch, fake_system_bus
):
    object_manager = Mock()
    object_manager.GetManagedObjects.return_value = {}
    monkeypatch.setattr(
        bluez_api.dbus,
        "Interface",
        Mock(return_value=object_manager),
    )

    with pytest.raises(bluez_api.BluetoothError, match="Scan for devices first"):
        bluez_api.pair_bluetooth_device("AA:BB:CC:DD:EE:FF")


def test_pair_bluetooth_device_raises_dbus_exception(monkeypatch, fake_system_bus):
    device = Mock()
    device.Pair.side_effect = dbus.exceptions.DBusException("Pairing failed")
    monkeypatch.setattr(
        bluez_api,
        "_get_bluetooth_device_path",
        lambda _bus, _address: BLUETOOTH_DEVICE_PATH,
    )
    monkeypatch.setattr(bluez_api.dbus, "Interface", Mock(return_value=device))

    with pytest.raises(bluez_api.BluetoothError, match="Pairing failed"):
        bluez_api.pair_bluetooth_device("AA:BB:CC:DD:EE:FF")


@pytest.mark.parametrize(
    ("function_name", "proxy_path", "interface_name", "method_name", "method_args"),
    [
        (
            "connect_bluetooth_device",
            BLUETOOTH_DEVICE_PATH,
            bluez_api.BLUEZ_DEVICE_INTERFACE,
            "Connect",
            (),
        ),
        (
            "disconnect_bluetooth_device",
            BLUETOOTH_DEVICE_PATH,
            bluez_api.BLUEZ_DEVICE_INTERFACE,
            "Disconnect",
            (),
        ),
        (
            "forget_bluetooth_device",
            bluez_api.ADAPTER_PATH,
            bluez_api.BLUEZ_ADAPTER_INTERFACE,
            "RemoveDevice",
            (BLUETOOTH_DEVICE_PATH,),
        ),
    ],
    ids=["connect", "disconnect", "forget"],
)
def test_control_bluetooth_device(
    monkeypatch,
    fake_system_bus,
    function_name,
    proxy_path,
    interface_name,
    method_name,
    method_args,
):
    target = Mock()
    interface = Mock(return_value=target)
    monkeypatch.setattr(
        bluez_api,
        "_get_bluetooth_device_path",
        lambda _bus, _address: BLUETOOTH_DEVICE_PATH,
    )
    monkeypatch.setattr(bluez_api.dbus, "Interface", interface)

    getattr(bluez_api, function_name)("AA:BB:CC:DD:EE:FF")

    assert fake_system_bus.get_object_calls == [(bluez_api.BLUEZ_SERVICE, proxy_path)]
    interface.assert_called_once_with(fake_system_bus.proxy, interface_name)
    getattr(target, method_name).assert_called_once_with(*method_args)


@pytest.mark.parametrize(
    ("function_name", "method_name"),
    [
        ("connect_bluetooth_device", "Connect"),
        ("disconnect_bluetooth_device", "Disconnect"),
        ("forget_bluetooth_device", "RemoveDevice"),
    ],
    ids=["connect", "disconnect", "forget"],
)
def test_control_bluetooth_device_raises_dbus_exception(
    monkeypatch,
    fake_system_bus,
    function_name,
    method_name,
):
    target = Mock()
    getattr(target, method_name).side_effect = dbus.exceptions.DBusException(
        "BlueZ failed"
    )
    monkeypatch.setattr(
        bluez_api,
        "_get_bluetooth_device_path",
        lambda _bus, _address: BLUETOOTH_DEVICE_PATH,
    )
    monkeypatch.setattr(bluez_api.dbus, "Interface", Mock(return_value=target))

    with pytest.raises(bluez_api.BluetoothError, match="BlueZ failed"):
        getattr(bluez_api, function_name)("AA:BB:CC:DD:EE:FF")
