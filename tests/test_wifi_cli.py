import argparse
import json
from io import StringIO

import pytest

from desktopctl.wifi import nmcli_api, wifi_cli


@pytest.mark.parametrize(
    ("enabled", "expected_output"),
    [(True, "enabled\n"), (False, "disabled\n")],
    ids=["enabled", "disabled"],
)
def test_status(monkeypatch: pytest.MonkeyPatch, capsys, enabled, expected_output):
    monkeypatch.setattr(wifi_cli, "wifi_is_enabled", lambda: enabled)

    result = wifi_cli._status(argparse.Namespace(json=False))

    assert result == 0
    assert capsys.readouterr().out == expected_output


@pytest.mark.parametrize(
    "enabled",
    [True, False],
    ids=["enabled", "disabled"],
)
def test_status_json(monkeypatch: pytest.MonkeyPatch, capsys, enabled):
    monkeypatch.setattr(wifi_cli, "wifi_is_enabled", lambda: enabled)

    result = wifi_cli._status(argparse.Namespace(json=True))
    output = json.loads(capsys.readouterr().out)

    assert result == 0
    assert output == {"enabled": enabled}


def test_list_visible(monkeypatch: pytest.MonkeyPatch, capsys):
    networks = [
        nmcli_api.WifiNetwork("Dummy WiFi", 67, "WPA2", False),
        nmcli_api.WifiNetwork("WiFi", 8, "--", True),
    ]
    monkeypatch.setattr(wifi_cli, "list_visible_wifi_networks", lambda: networks)

    result = wifi_cli._list_visible(argparse.Namespace(json=False))

    assert result == 0
    assert capsys.readouterr().out == (
        "SSID        SIGNAL  SECURITY  CONNECTED\n"
        "Dummy WiFi  67      WPA2      false\n"
        "WiFi        8       --        true\n"
    )


def test_list_visible_json(monkeypatch: pytest.MonkeyPatch, capsys):
    networks = [
        nmcli_api.WifiNetwork("Dummy WiFi", 67, "WPA2", False),
        nmcli_api.WifiNetwork("WiFi", 8, "--", True),
    ]
    monkeypatch.setattr(wifi_cli, "list_visible_wifi_networks", lambda: networks)

    result = wifi_cli._list_visible(argparse.Namespace(json=True))
    output = json.loads(capsys.readouterr().out)

    assert result == 0
    assert output == [
        {
            "ssid": "Dummy WiFi",
            "signal": 67,
            "security": "WPA2",
            "connected": False,
        },
        {"ssid": "WiFi", "signal": 8, "security": "--", "connected": True},
    ]


def test_list_saved(monkeypatch: pytest.MonkeyPatch, capsys):
    profiles = [
        nmcli_api.SavedWifiProfile("123abc", "Dummy", "Dummy WiFi"),
        nmcli_api.SavedWifiProfile("456def", "Work profile", "Work"),
    ]
    monkeypatch.setattr(wifi_cli, "list_saved_wifi_networks", lambda: profiles)

    result = wifi_cli._list_saved(argparse.Namespace(json=False))

    assert result == 0
    assert capsys.readouterr().out == (
        "SSID        NAME          UUID\n"
        "Dummy WiFi  Dummy         123abc\n"
        "Work        Work profile  456def\n"
    )


def test_list_saved_json(monkeypatch: pytest.MonkeyPatch, capsys):
    profiles = [
        nmcli_api.SavedWifiProfile("123abc", "Dummy", "Dummy WiFi"),
        nmcli_api.SavedWifiProfile("456def", "Work profile", "Work"),
    ]
    monkeypatch.setattr(wifi_cli, "list_saved_wifi_networks", lambda: profiles)

    result = wifi_cli._list_saved(argparse.Namespace(json=True))
    output = json.loads(capsys.readouterr().out)

    assert result == 0
    assert output == [
        {"ssid": "Dummy WiFi", "name": "Dummy", "uuid": "123abc"},
        {"ssid": "Work", "name": "Work profile", "uuid": "456def"},
    ]


@pytest.mark.parametrize(
    ("password_stdin", "stdin_text", "expected_password"),
    [(False, "", None), (True, "1234!\n", "1234!")],
    ids=["without-password", "with-password"],
)
def test_connect(
    monkeypatch: pytest.MonkeyPatch,
    password_stdin,
    stdin_text,
    expected_password,
):
    def fake_connect_wifi_network(ssid, password):
        assert ssid == "WiFi"
        assert password == expected_password

    monkeypatch.setattr(wifi_cli, "connect_wifi_network", fake_connect_wifi_network)
    monkeypatch.setattr(wifi_cli.sys, "stdin", StringIO(stdin_text))
    arguments = argparse.Namespace(ssid="WiFi", password_stdin=password_stdin)

    assert wifi_cli._connect(arguments) == 0


def test_connect_raises_error_for_empty_password(monkeypatch: pytest.MonkeyPatch):
    def fake_connect_wifi_network(ssid, password):
        pytest.fail("connect_wifi_network must not be called")

    monkeypatch.setattr(wifi_cli, "connect_wifi_network", fake_connect_wifi_network)
    monkeypatch.setattr(wifi_cli.sys, "stdin", StringIO("\n"))
    arguments = argparse.Namespace(ssid="WiFi", password_stdin=True)

    with pytest.raises(wifi_cli.WifiError, match="No WiFi password was provided"):
        wifi_cli._connect(arguments)


@pytest.mark.parametrize(
    ("cli_arguments", "expected_handler", "expected_values"),
    [
        (["status"], wifi_cli._status, {"json": False}),
        (["visible", "--json"], wifi_cli._list_visible, {"json": True}),
        (["saved", "--json"], wifi_cli._list_saved, {"json": True}),
        (["enable"], wifi_cli._enable, {}),
        (["disable"], wifi_cli._disable, {}),
        (["scan"], wifi_cli._scan, {}),
        (
            ["connect", "WiFi", "--password-stdin"],
            wifi_cli._connect,
            {"ssid": "WiFi", "password_stdin": True},
        ),
        (["disconnect"], wifi_cli._disconnect, {}),
        (["forget", "123abc"], wifi_cli._forget, {"uuid": "123abc"}),
    ],
    ids=[
        "status",
        "visible",
        "saved",
        "enable",
        "disable",
        "scan",
        "connect",
        "disconnect",
        "forget",
    ],
)
def test_configure_wifi_parser(cli_arguments, expected_handler, expected_values):
    parser = argparse.ArgumentParser()
    wifi_cli.configure_wifi_parser(parser)

    arguments = parser.parse_args(cli_arguments)

    assert arguments.handler is expected_handler
    for name, value in expected_values.items():
        assert getattr(arguments, name) == value
