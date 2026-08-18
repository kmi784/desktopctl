import argparse
import json
from unittest.mock import Mock

import pytest

from desktopctl.brightness import brightness_cli


def test_get(monkeypatch: pytest.MonkeyPatch, capsys):
    monkeypatch.setattr(brightness_cli, "get_brightness", Mock(return_value=61))

    result = brightness_cli._get(argparse.Namespace(json=False))

    assert result == 0
    assert capsys.readouterr().out == "61\n"


def test_get_json(monkeypatch: pytest.MonkeyPatch, capsys):
    monkeypatch.setattr(brightness_cli, "get_brightness", Mock(return_value=61))

    result = brightness_cli._get(argparse.Namespace(json=True))
    output = json.loads(capsys.readouterr().out)

    assert result == 0
    assert output == {"brightness": 61}


def test_set(monkeypatch: pytest.MonkeyPatch):
    set_brightness = Mock()
    monkeypatch.setattr(brightness_cli, "set_brightness", set_brightness)

    result = brightness_cli._set(argparse.Namespace(percentage=50))

    assert result == 0
    set_brightness.assert_called_once_with(50)


@pytest.mark.parametrize("percentage", [-1, 101], ids=["below-minimum", "above-maximum"])
def test_set_rejects_invalid_percentage(
    monkeypatch: pytest.MonkeyPatch,
    percentage: int,
):
    set_brightness = Mock()
    monkeypatch.setattr(brightness_cli, "set_brightness", set_brightness)

    with pytest.raises(brightness_cli.BrightnessError, match="between 0 and 100"):
        brightness_cli._set(argparse.Namespace(percentage=percentage))

    set_brightness.assert_not_called()


def test_change(monkeypatch: pytest.MonkeyPatch):
    change_brightness = Mock()
    monkeypatch.setattr(brightness_cli, "change_brightness", change_brightness)

    result = brightness_cli._change(argparse.Namespace(delta=-10))

    assert result == 0
    change_brightness.assert_called_once_with(-10)


@pytest.mark.parametrize(
    ("cli_arguments", "expected_handler", "expected_values"),
    [
        (["get"], brightness_cli._get, {"json": False}),
        (["get", "--json"], brightness_cli._get, {"json": True}),
        (["set", "50"], brightness_cli._set, {"percentage": 50}),
        (["change", "10"], brightness_cli._change, {"delta": 10}),
        (["change", "-10"], brightness_cli._change, {"delta": -10}),
    ],
    ids=["get", "get-json", "set", "increase", "decrease"],
)
def test_configure_brightness_parser(
    cli_arguments,
    expected_handler,
    expected_values,
):
    parser = argparse.ArgumentParser()
    brightness_cli.configure_brightness_parser(parser)

    arguments = parser.parse_args(cli_arguments)

    assert arguments.handler is expected_handler
    for name, value in expected_values.items():
        assert getattr(arguments, name) == value
