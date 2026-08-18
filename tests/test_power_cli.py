import argparse
import json
from unittest.mock import Mock

import pytest

from desktopctl.power import power_cli, upower_api


def _configure_power_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configure representative power status data for CLI tests."""
    monkeypatch.setattr(
        power_cli,
        "get_battery_status",
        lambda: upower_api.BatteryStatus(73, True),
    )
    monkeypatch.setattr(power_cli, "device_is_ac_connected", lambda: True)
    monkeypatch.setattr(
        power_cli,
        "get_power_profile",
        lambda: upower_api.PowerProfile.BALANCED,
    )


def _power_status_data() -> dict[str, object]:
    """Return the expected serialized power status."""
    return {
        "battery": 73,
        "charging": True,
        "connected": True,
        "profile": "balanced",
    }


def test_status(monkeypatch: pytest.MonkeyPatch):
    _configure_power_status(monkeypatch)
    print_table = Mock()
    monkeypatch.setattr(power_cli, "print_table", print_table)

    result = power_cli._status(argparse.Namespace(json=False))

    assert result == 0
    print_table.assert_called_once_with([_power_status_data()])


def test_status_json(monkeypatch: pytest.MonkeyPatch, capsys):
    _configure_power_status(monkeypatch)

    result = power_cli._status(argparse.Namespace(json=True))
    output = json.loads(capsys.readouterr().out)

    assert result == 0
    assert output == _power_status_data()


def test_profile(monkeypatch: pytest.MonkeyPatch):
    set_power_profile = Mock()
    monkeypatch.setattr(power_cli, "set_power_profile", set_power_profile)

    result = power_cli._profile(
        argparse.Namespace(profile=upower_api.PowerProfile.PERFORMANCE)
    )

    assert result == 0
    set_power_profile.assert_called_once_with(upower_api.PowerProfile.PERFORMANCE)


@pytest.mark.parametrize(
    ("cli_arguments", "expected_handler", "expected_values"),
    [
        (["status"], power_cli._status, {"json": False}),
        (["status", "--json"], power_cli._status, {"json": True}),
        (
            ["profile", "power-saver"],
            power_cli._profile,
            {"profile": upower_api.PowerProfile.POWER_SAVER},
        ),
    ],
    ids=["status", "status-json", "profile"],
)
def test_configure_power_parser(
    cli_arguments,
    expected_handler,
    expected_values,
):
    parser = argparse.ArgumentParser()
    power_cli.configure_power_parser(parser)

    arguments = parser.parse_args(cli_arguments)

    assert arguments.handler is expected_handler
    for name, value in expected_values.items():
        assert getattr(arguments, name) == value
