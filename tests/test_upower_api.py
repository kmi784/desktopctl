from unittest.mock import Mock

import dbus
import pytest

from desktopctl.power import upower_api


@pytest.fixture
def fake_system_bus(system_bus_factory):
    return system_bus_factory(upower_api)


@pytest.mark.parametrize(
    ("present", "percentage", "state", "expected"),
    [
        (False, 0.0, 0, upower_api.BatteryStatus(None, None)),
        (True, 66.6, 1, upower_api.BatteryStatus(67, True)),
        (True, 40.2, 2, upower_api.BatteryStatus(40, False)),
    ],
    ids=["not-present", "charging", "discharging"],
)
def test_get_battery_status(
    monkeypatch: pytest.MonkeyPatch,
    fake_system_bus,
    present,
    percentage,
    state,
    expected,
):
    properties = Mock()
    properties.GetAll.return_value = {
        "IsPresent": dbus.Boolean(present),
        "Percentage": dbus.Double(percentage),
        "State": dbus.UInt32(state),
    }
    interface = Mock(return_value=properties)
    monkeypatch.setattr(upower_api.dbus, "Interface", interface)

    assert upower_api.get_battery_status() == expected
    assert fake_system_bus.get_object_calls == [
        (upower_api.UPOWER_SERVICE, upower_api.UPOWER_DEVICE_PATH)
    ]
    interface.assert_called_once_with(fake_system_bus.proxy, dbus.PROPERTIES_IFACE)
    properties.GetAll.assert_called_once_with(upower_api.UPOWER_DEVICE_INTERFACE)


def test_get_battery_status_raises_dbus_exception(
    monkeypatch: pytest.MonkeyPatch,
    fake_system_bus,
):
    properties = Mock()
    properties.GetAll.side_effect = dbus.exceptions.DBusException("UPower failed")
    monkeypatch.setattr(upower_api.dbus, "Interface", Mock(return_value=properties))

    with pytest.raises(upower_api.PowerError, match="UPower failed"):
        upower_api.get_battery_status()


@pytest.mark.parametrize(
    ("on_battery", "expected"),
    [(True, False), (False, True)],
    ids=["on-battery", "external-power"],
)
def test_device_is_ac_connected(
    monkeypatch: pytest.MonkeyPatch,
    fake_system_bus,
    on_battery,
    expected,
):
    properties = Mock()
    properties.Get.return_value = dbus.Boolean(on_battery)
    interface = Mock(return_value=properties)
    monkeypatch.setattr(upower_api.dbus, "Interface", interface)

    assert upower_api.device_is_ac_connected() is expected
    assert fake_system_bus.get_object_calls == [
        (upower_api.UPOWER_SERVICE, upower_api.UPOWER_PATH)
    ]
    interface.assert_called_once_with(fake_system_bus.proxy, dbus.PROPERTIES_IFACE)
    properties.Get.assert_called_once_with(upower_api.UPOWER_SERVICE, "OnBattery")


def test_device_is_ac_connected_raises_dbus_exception(
    monkeypatch: pytest.MonkeyPatch,
    fake_system_bus,
):
    properties = Mock()
    properties.Get.side_effect = dbus.exceptions.DBusException("UPower failed")
    monkeypatch.setattr(upower_api.dbus, "Interface", Mock(return_value=properties))

    with pytest.raises(upower_api.PowerError, match="UPower failed"):
        upower_api.device_is_ac_connected()


@pytest.mark.parametrize(
    "profile",
    list(upower_api.PowerProfile),
    ids=lambda profile: profile.value,
)
def test_get_power_profile(
    monkeypatch: pytest.MonkeyPatch,
    fake_system_bus,
    profile,
):
    properties = Mock()
    properties.Get.return_value = dbus.String(profile.value)
    interface = Mock(return_value=properties)
    monkeypatch.setattr(upower_api.dbus, "Interface", interface)

    assert upower_api.get_power_profile() is profile
    assert fake_system_bus.get_object_calls == [
        (upower_api.POWER_PROFILE_SERVICE, upower_api.POWER_PROFILE_PATH)
    ]
    interface.assert_called_once_with(fake_system_bus.proxy, dbus.PROPERTIES_IFACE)
    properties.Get.assert_called_once_with(
        upower_api.POWER_PROFILE_SERVICE,
        "ActiveProfile",
    )


def test_get_power_profile_rejects_unknown_profile(
    monkeypatch: pytest.MonkeyPatch,
    fake_system_bus,
):
    properties = Mock()
    properties.Get.return_value = dbus.String("unknown")
    monkeypatch.setattr(upower_api.dbus, "Interface", Mock(return_value=properties))

    with pytest.raises(upower_api.PowerError, match="Unsupported power profile"):
        upower_api.get_power_profile()


def test_get_power_profile_raises_dbus_exception(
    monkeypatch: pytest.MonkeyPatch,
    fake_system_bus,
):
    properties = Mock()
    properties.Get.side_effect = dbus.exceptions.DBusException("Power Profiles failed")
    monkeypatch.setattr(upower_api.dbus, "Interface", Mock(return_value=properties))

    with pytest.raises(upower_api.PowerError, match="Power Profiles failed"):
        upower_api.get_power_profile()


@pytest.mark.parametrize(
    "profile",
    list(upower_api.PowerProfile),
    ids=lambda profile: profile.value,
)
def test_set_power_profile(
    monkeypatch: pytest.MonkeyPatch,
    fake_system_bus,
    profile,
):
    properties = Mock()
    interface = Mock(return_value=properties)
    monkeypatch.setattr(upower_api.dbus, "Interface", interface)

    upower_api.set_power_profile(profile)

    assert fake_system_bus.get_object_calls == [
        (upower_api.POWER_PROFILE_SERVICE, upower_api.POWER_PROFILE_PATH)
    ]
    interface.assert_called_once_with(fake_system_bus.proxy, dbus.PROPERTIES_IFACE)
    interface_name, property_name, property_value = properties.Set.call_args.args
    assert interface_name == upower_api.POWER_PROFILE_SERVICE
    assert property_name == "ActiveProfile"
    assert type(property_value) is dbus.String
    assert str(property_value) == profile.value


def test_set_power_profile_raises_dbus_exception(
    monkeypatch: pytest.MonkeyPatch,
    fake_system_bus,
):
    properties = Mock()
    properties.Set.side_effect = dbus.exceptions.DBusException("Power Profiles failed")
    monkeypatch.setattr(upower_api.dbus, "Interface", Mock(return_value=properties))

    with pytest.raises(upower_api.PowerError, match="Power Profiles failed"):
        upower_api.set_power_profile(upower_api.PowerProfile.BALANCED)
