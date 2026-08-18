from pathlib import Path
from unittest.mock import Mock

import dbus
import pytest

from desktopctl.brightness import backlight_api


@pytest.fixture
def fake_system_bus(system_bus_factory):
    return system_bus_factory(backlight_api)


@pytest.fixture
def backlight_device(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    """Return a simulated backlight device in a temporary sysfs tree."""
    backlight_root = tmp_path / "backlight"
    backlight_root.mkdir()
    device_path = backlight_root / "intel_backlight"
    device_path.mkdir()
    monkeypatch.setattr(backlight_api, "BACKLIGHT_ROOT", backlight_root)
    return device_path


def _write_attribute(device_path: Path, name: str, value: object) -> None:
    """Write a simulated backlight attribute."""
    (device_path / name).write_text(str(value), encoding="ascii")


@pytest.mark.parametrize(
    ("brightness", "max_brightness", "expected"),
    [
        (0, 400, 0),
        (123, 200, 62),
        (400, 400, 100),
    ],
    ids=["minimum", "rounded", "maximum"],
)
def test_get_brightness(
    backlight_device: Path,
    brightness: int,
    max_brightness: int,
    expected: int,
):
    _write_attribute(backlight_device, "brightness", brightness)
    _write_attribute(backlight_device, "max_brightness", max_brightness)

    assert backlight_api.get_brightness() == expected


def test_get_brightness_raises_error_without_device(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    backlight_root = tmp_path / "backlight"
    backlight_root.mkdir()
    monkeypatch.setattr(backlight_api, "BACKLIGHT_ROOT", backlight_root)

    with pytest.raises(backlight_api.BrightnessError, match="No backlight device"):
        backlight_api.get_brightness()


def test_get_brightness_raises_error_with_multiple_devices(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    backlight_root = tmp_path / "backlight"
    backlight_root.mkdir()
    (backlight_root / "device-one").mkdir()
    (backlight_root / "device-two").mkdir()
    monkeypatch.setattr(backlight_api, "BACKLIGHT_ROOT", backlight_root)

    with pytest.raises(
        backlight_api.BrightnessError,
        match="Multiple backlight devices",
    ):
        backlight_api.get_brightness()


def test_get_brightness_raises_error_when_sysfs_is_unavailable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(backlight_api, "BACKLIGHT_ROOT", tmp_path / "missing")

    with pytest.raises(backlight_api.BrightnessError, match="list backlight devices"):
        backlight_api.get_brightness()


@pytest.mark.parametrize(
    ("attribute", "value"),
    [("brightness", "invalid"), ("max_brightness", "invalid")],
    ids=["brightness", "max-brightness"],
)
def test_get_brightness_raises_error_for_invalid_attribute(
    backlight_device: Path,
    attribute: str,
    value: str,
):
    _write_attribute(backlight_device, "brightness", 50)
    _write_attribute(backlight_device, "max_brightness", 100)
    _write_attribute(backlight_device, attribute, value)

    with pytest.raises(backlight_api.BrightnessError, match="read backlight attribute"):
        backlight_api.get_brightness()


def test_get_brightness_raises_error_for_missing_attribute(
    backlight_device: Path,
):
    _write_attribute(backlight_device, "max_brightness", 100)

    with pytest.raises(backlight_api.BrightnessError, match="read backlight attribute"):
        backlight_api.get_brightness()


@pytest.mark.parametrize("max_brightness", [0, -1], ids=["zero", "negative"])
def test_get_brightness_rejects_invalid_maximum(
    backlight_device: Path,
    max_brightness: int,
):
    _write_attribute(backlight_device, "brightness", 0)
    _write_attribute(backlight_device, "max_brightness", max_brightness)

    with pytest.raises(backlight_api.BrightnessError, match="Invalid maximum"):
        backlight_api.get_brightness()


def test_set_brightness(
    monkeypatch: pytest.MonkeyPatch,
    fake_system_bus,
    backlight_device: Path,
):
    _write_attribute(backlight_device, "max_brightness", 38787)
    session = Mock()
    interface = Mock(return_value=session)
    monkeypatch.setattr(backlight_api.dbus, "Interface", interface)

    backlight_api.set_brightness(50)

    assert fake_system_bus.get_object_calls == [
        (backlight_api.LOGIN1_SERVICE, backlight_api.LOGIN1_SESSION_PATH)
    ]
    interface.assert_called_once_with(
        fake_system_bus.proxy,
        backlight_api.LOGIN1_SESSION_INTERFACE,
    )
    subsystem, device_name, raw_brightness = session.SetBrightness.call_args.args
    assert subsystem == "backlight"
    assert device_name == "intel_backlight"
    assert type(raw_brightness) is dbus.UInt32
    assert int(raw_brightness) == 19394


def test_set_brightness_rejects_invalid_maximum(
    monkeypatch: pytest.MonkeyPatch,
    fake_system_bus,
    backlight_device: Path,
):
    _write_attribute(backlight_device, "max_brightness", 0)
    session = Mock()
    monkeypatch.setattr(backlight_api.dbus, "Interface", Mock(return_value=session))

    with pytest.raises(backlight_api.BrightnessError, match="Invalid maximum"):
        backlight_api.set_brightness(50)

    session.SetBrightness.assert_not_called()


def test_set_brightness_raises_dbus_exception(
    monkeypatch: pytest.MonkeyPatch,
    fake_system_bus,
    backlight_device: Path,
):
    _write_attribute(backlight_device, "max_brightness", 100)
    session = Mock()
    session.SetBrightness.side_effect = dbus.exceptions.DBusException("logind failed")
    monkeypatch.setattr(backlight_api.dbus, "Interface", Mock(return_value=session))

    with pytest.raises(backlight_api.BrightnessError, match="logind failed"):
        backlight_api.set_brightness(50)


@pytest.mark.parametrize(
    ("current", "delta", "expected"),
    [
        (50, 10, 60),
        (95, 10, 100),
        (5, -10, 0),
    ],
    ids=["change", "upper-bound", "lower-bound"],
)
def test_change_brightness(
    monkeypatch: pytest.MonkeyPatch,
    current: int,
    delta: int,
    expected: int,
):
    get_brightness = Mock(return_value=current)
    set_brightness = Mock()
    monkeypatch.setattr(backlight_api, "get_brightness", get_brightness)
    monkeypatch.setattr(backlight_api, "set_brightness", set_brightness)

    backlight_api.change_brightness(delta)

    get_brightness.assert_called_once_with()
    set_brightness.assert_called_once_with(expected)
