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


def _configure_pairing(
    monkeypatch: pytest.MonkeyPatch,
    fake_system_bus,
    *,
    initially_paired: bool = False,
    initially_bonded: bool = False,
    paired: bool = True,
    bonded: bool = True,
    pairing_error: dbus.exceptions.DBusException | None = None,
):
    """Configure test doubles for the BlueZ pairing workflow."""
    bluez_proxy = object()
    device_proxy = object()
    agent_manager_proxy = object()
    fake_system_bus.proxies.update(
        {
            BLUEZ_ROOT_PATH: bluez_proxy,
            BLUETOOTH_DEVICE_PATH: device_proxy,
            bluez_api.BLUEZ_AGENT_MANAGER_PATH: agent_manager_proxy,
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
    properties = Mock()
    pairing_states = (
        {"Paired": initially_paired, "Bonded": initially_bonded},
        {"Paired": paired, "Bonded": bonded},
    )
    property_get_count = 0

    def _get_property(_interface, name):
        nonlocal property_get_count
        state = pairing_states[min(property_get_count // 2, 1)]
        property_get_count += 1
        return dbus.Boolean(state[name])

    properties.Get.side_effect = _get_property
    agent_manager = Mock()
    agent = Mock()
    main_loop = Mock()
    pairing_callbacks = {}

    def _pair(**kwargs):
        pairing_callbacks.update(kwargs)

    def _run_main_loop():
        if pairing_error is None:
            pairing_callbacks["reply_handler"]()
        else:
            pairing_callbacks["error_handler"](pairing_error)

    device.Pair.side_effect = _pair
    main_loop.run.side_effect = _run_main_loop

    def fake_interface(proxy, interface_name):
        if proxy is bluez_proxy:
            assert interface_name == bluez_api.DBUS_OBJECT_MANAGER_INTERFACE
            return object_manager

        if proxy is device_proxy:
            if interface_name == bluez_api.BLUEZ_DEVICE_INTERFACE:
                return device

            assert interface_name == dbus.PROPERTIES_IFACE
            return properties

        assert proxy is agent_manager_proxy
        assert interface_name == bluez_api.BLUEZ_AGENT_MANAGER_INTERFACE
        return agent_manager

    monkeypatch.setattr(bluez_api.dbus, "Interface", fake_interface)
    dbus_main_loop = Mock()
    monkeypatch.setattr(
        bluez_api,
        "DBusGMainLoop",
        Mock(return_value=dbus_main_loop),
    )
    monkeypatch.setattr(bluez_api, "BlueZAgent", Mock(return_value=agent))
    monkeypatch.setattr(bluez_api.GLib, "MainLoop", Mock(return_value=main_loop))

    return device, properties, agent_manager, agent, main_loop


def test_pair_bluetooth_device(monkeypatch, fake_system_bus):
    device, properties, agent_manager, agent, main_loop = _configure_pairing(
        monkeypatch,
        fake_system_bus,
    )

    bluez_api.pair_bluetooth_device("aa:bb:cc:dd:ee:ff")

    bluez_api.DBusGMainLoop.assert_called_once_with()
    assert fake_system_bus.system_bus_calls == [
        ((), {"private": True, "mainloop": bluez_api.DBusGMainLoop.return_value})
    ]
    assert fake_system_bus.get_object_calls == [
        (bluez_api.BLUEZ_SERVICE, BLUEZ_ROOT_PATH),
        (bluez_api.BLUEZ_SERVICE, BLUETOOTH_DEVICE_PATH),
        (bluez_api.BLUEZ_SERVICE, bluez_api.BLUEZ_AGENT_MANAGER_PATH),
    ]
    bluez_api.BlueZAgent.assert_called_once_with(
        fake_system_bus,
        BLUETOOTH_DEVICE_PATH,
    )
    agent_manager.RegisterAgent.assert_called_once_with(
        bluez_api.BLUEZ_AGENT_PATH,
        bluez_api.BLUEZ_AGENT_CAPABILITY,
    )
    assert device.Pair.call_count == 1
    assert device.Pair.call_args.kwargs["timeout"] == bluez_api.PAIRING_TIMEOUT
    assert callable(device.Pair.call_args.kwargs["reply_handler"])
    assert callable(device.Pair.call_args.kwargs["error_handler"])
    main_loop.run.assert_called_once_with()
    assert properties.Get.call_args_list == [
        ((bluez_api.BLUEZ_DEVICE_INTERFACE, "Paired"),),
        ((bluez_api.BLUEZ_DEVICE_INTERFACE, "Bonded"),),
        ((bluez_api.BLUEZ_DEVICE_INTERFACE, "Paired"),),
        ((bluez_api.BLUEZ_DEVICE_INTERFACE, "Bonded"),),
    ]
    interface_name, property_name, property_value = properties.Set.call_args.args
    assert interface_name == bluez_api.BLUEZ_DEVICE_INTERFACE
    assert property_name == "Trusted"
    assert type(property_value) is dbus.Boolean
    assert bool(property_value) is True
    agent_manager.UnregisterAgent.assert_called_once_with(bluez_api.BLUEZ_AGENT_PATH)
    agent.remove_from_connection.assert_called_once_with()
    fake_system_bus.close.assert_called_once_with()


def test_pair_bluetooth_device_trusts_existing_pairing(
    monkeypatch,
    fake_system_bus,
):
    device, properties, agent_manager, agent, main_loop = _configure_pairing(
        monkeypatch,
        fake_system_bus,
        initially_paired=True,
        initially_bonded=True,
    )

    bluez_api.pair_bluetooth_device("AA:BB:CC:DD:EE:FF")

    device.Pair.assert_not_called()
    bluez_api.BlueZAgent.assert_not_called()
    agent_manager.RegisterAgent.assert_not_called()
    main_loop.run.assert_not_called()
    properties.Set.assert_called_once()
    assert properties.Set.call_args.args[:2] == (
        bluez_api.BLUEZ_DEVICE_INTERFACE,
        "Trusted",
    )
    agent.remove_from_connection.assert_not_called()
    fake_system_bus.close.assert_called_once_with()


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

    fake_system_bus.close.assert_called_once_with()


def test_pair_bluetooth_device_raises_dbus_exception(monkeypatch, fake_system_bus):
    pairing_error = dbus.exceptions.DBusException("Pairing failed")
    _device, properties, agent_manager, agent, _main_loop = _configure_pairing(
        monkeypatch,
        fake_system_bus,
        pairing_error=pairing_error,
    )

    with pytest.raises(bluez_api.BluetoothError, match="Pairing failed"):
        bluez_api.pair_bluetooth_device("AA:BB:CC:DD:EE:FF")

    assert properties.Get.call_count == 2
    properties.Set.assert_not_called()
    agent_manager.UnregisterAgent.assert_called_once_with(bluez_api.BLUEZ_AGENT_PATH)
    agent.remove_from_connection.assert_called_once_with()
    fake_system_bus.close.assert_called_once_with()


@pytest.mark.parametrize(
    ("paired", "bonded"),
    [(False, True), (True, False)],
    ids=["not-paired", "not-bonded"],
)
def test_pair_bluetooth_device_requires_persistent_pairing(
    monkeypatch,
    fake_system_bus,
    paired,
    bonded,
):
    _device, properties, agent_manager, agent, _main_loop = _configure_pairing(
        monkeypatch,
        fake_system_bus,
        paired=paired,
        bonded=bonded,
    )

    with pytest.raises(bluez_api.BluetoothError, match="not paired permanently"):
        bluez_api.pair_bluetooth_device("AA:BB:CC:DD:EE:FF")

    properties.Set.assert_not_called()
    agent_manager.UnregisterAgent.assert_called_once_with(bluez_api.BLUEZ_AGENT_PATH)
    agent.remove_from_connection.assert_called_once_with()
    fake_system_bus.close.assert_called_once_with()


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
