import argparse
import json
from unittest.mock import Mock

import pytest

from desktopctl.bluetooth import bluetooth_cli, bluez_api


def _bluetooth_devices() -> list[bluez_api.BluetoothDevice]:
    """Return representative Bluetooth devices for CLI tests."""
    return [
        bluez_api.BluetoothDevice(
            address="AA:BB:CC:DD:EE:FF",
            name="Headphones",
            rssi=-42,
            battery=73,
            paired=True,
            connected=True,
        ),
        bluez_api.BluetoothDevice(
            address="11:22:33:44:55:66",
            name=None,
            rssi=None,
            battery=None,
            paired=False,
            connected=False,
        ),
    ]


def _device_data() -> list[dict[str, object]]:
    """Return the expected serialized device data."""
    return [
        {
            "address": "AA:BB:CC:DD:EE:FF",
            "name": "Headphones",
            "rssi": -42,
            "battery": 73,
            "paired": True,
            "connected": True,
        },
        {
            "address": "11:22:33:44:55:66",
            "name": None,
            "rssi": None,
            "battery": None,
            "paired": False,
            "connected": False,
        },
    ]


@pytest.mark.parametrize(
    ("enabled", "expected_output"),
    [(True, "enabled\n"), (False, "disabled\n")],
    ids=["enabled", "disabled"],
)
def test_status(monkeypatch: pytest.MonkeyPatch, capsys, enabled, expected_output):
    monkeypatch.setattr(bluetooth_cli, "bluetooth_is_enabled", lambda: enabled)

    result = bluetooth_cli._status(argparse.Namespace(json=False))

    assert result == 0
    assert capsys.readouterr().out == expected_output


def test_status_json(monkeypatch: pytest.MonkeyPatch, capsys):
    devices = _bluetooth_devices()
    monkeypatch.setattr(bluetooth_cli, "bluetooth_is_enabled", lambda: True)
    monkeypatch.setattr(
        bluetooth_cli,
        "list_connected_bluetooth_devices",
        lambda: devices,
    )

    result = bluetooth_cli._status(argparse.Namespace(json=True))
    output = json.loads(capsys.readouterr().out)

    assert result == 0
    assert output == {
        "enabled": True,
        "connected_devices": _device_data(),
    }


def test_list_visible(monkeypatch: pytest.MonkeyPatch):
    print_table = Mock()
    monkeypatch.setattr(
        bluetooth_cli,
        "list_visible_bluetooth_devices",
        _bluetooth_devices,
    )
    monkeypatch.setattr(bluetooth_cli, "print_table", print_table)

    result = bluetooth_cli._list_visible(argparse.Namespace(json=False))

    assert result == 0
    print_table.assert_called_once_with(_device_data())


def test_list_visible_json(monkeypatch: pytest.MonkeyPatch, capsys):
    monkeypatch.setattr(
        bluetooth_cli,
        "list_visible_bluetooth_devices",
        _bluetooth_devices,
    )

    result = bluetooth_cli._list_visible(argparse.Namespace(json=True))
    output = json.loads(capsys.readouterr().out)

    assert result == 0
    assert output == _device_data()


def test_list_paired(monkeypatch: pytest.MonkeyPatch):
    print_table = Mock()
    monkeypatch.setattr(
        bluetooth_cli,
        "list_paired_bluetooth_devices",
        _bluetooth_devices,
    )
    monkeypatch.setattr(bluetooth_cli, "print_table", print_table)

    result = bluetooth_cli._list_paired(argparse.Namespace(json=False))

    assert result == 0
    print_table.assert_called_once_with(_device_data())


def test_list_paired_json(monkeypatch: pytest.MonkeyPatch, capsys):
    monkeypatch.setattr(
        bluetooth_cli,
        "list_paired_bluetooth_devices",
        _bluetooth_devices,
    )

    result = bluetooth_cli._list_paired(argparse.Namespace(json=True))
    output = json.loads(capsys.readouterr().out)

    assert result == 0
    assert output == _device_data()


@pytest.mark.parametrize(
    ("handler_name", "enabled"),
    [("_enable", True), ("_disable", False)],
    ids=["enable", "disable"],
)
def test_set_bluetooth_state(
    monkeypatch: pytest.MonkeyPatch,
    handler_name,
    enabled,
):
    enable_bluetooth = Mock()
    monkeypatch.setattr(bluetooth_cli, "enable_bluetooth", enable_bluetooth)

    handler = getattr(bluetooth_cli, handler_name)
    assert handler(argparse.Namespace()) == 0
    enable_bluetooth.assert_called_once_with(enabled)


def test_scan(monkeypatch: pytest.MonkeyPatch):
    scan_bluetooth_devices = Mock()
    monkeypatch.setattr(
        bluetooth_cli,
        "scan_bluetooth_devices",
        scan_bluetooth_devices,
    )

    assert bluetooth_cli._scan(argparse.Namespace()) == 0
    scan_bluetooth_devices.assert_called_once_with()


@pytest.mark.parametrize(
    ("handler_name", "function_name"),
    [
        ("_pair", "pair_bluetooth_device"),
        ("_connect", "connect_bluetooth_device"),
        ("_disconnect", "disconnect_bluetooth_device"),
        ("_forget", "forget_bluetooth_device"),
    ],
    ids=["pair", "connect", "disconnect", "forget"],
)
def test_device_action(
    monkeypatch: pytest.MonkeyPatch,
    handler_name,
    function_name,
):
    action = Mock()
    monkeypatch.setattr(bluetooth_cli, function_name, action)

    handler = getattr(bluetooth_cli, handler_name)
    assert handler(argparse.Namespace(address="AA:BB:CC:DD:EE:FF")) == 0
    action.assert_called_once_with("AA:BB:CC:DD:EE:FF")


@pytest.mark.parametrize(
    ("cli_arguments", "expected_handler", "expected_values"),
    [
        (["status", "--json"], bluetooth_cli._status, {"json": True}),
        (["visible"], bluetooth_cli._list_visible, {"json": False}),
        (["paired", "--json"], bluetooth_cli._list_paired, {"json": True}),
        (["enable"], bluetooth_cli._enable, {}),
        (["disable"], bluetooth_cli._disable, {}),
        (["scan"], bluetooth_cli._scan, {}),
        (
            ["pair", "AA:BB:CC:DD:EE:FF"],
            bluetooth_cli._pair,
            {"address": "AA:BB:CC:DD:EE:FF"},
        ),
        (
            ["connect", "AA:BB:CC:DD:EE:FF"],
            bluetooth_cli._connect,
            {"address": "AA:BB:CC:DD:EE:FF"},
        ),
        (
            ["disconnect", "AA:BB:CC:DD:EE:FF"],
            bluetooth_cli._disconnect,
            {"address": "AA:BB:CC:DD:EE:FF"},
        ),
        (
            ["forget", "AA:BB:CC:DD:EE:FF"],
            bluetooth_cli._forget,
            {"address": "AA:BB:CC:DD:EE:FF"},
        ),
    ],
    ids=[
        "status",
        "visible",
        "paired",
        "enable",
        "disable",
        "scan",
        "pair",
        "connect",
        "disconnect",
        "forget",
    ],
)
def test_configure_bluetooth_parser(
    cli_arguments,
    expected_handler,
    expected_values,
):
    parser = argparse.ArgumentParser()
    bluetooth_cli.configure_bluetooth_parser(parser)

    arguments = parser.parse_args(cli_arguments)

    assert arguments.handler is expected_handler
    for name, value in expected_values.items():
        assert getattr(arguments, name) == value
