import argparse
from unittest.mock import Mock

import pytest

from desktopctl.bluetooth import bluetooth_cli


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
def test_device_action(monkeypatch, handler_name, function_name):
    action = Mock()
    monkeypatch.setattr(bluetooth_cli, function_name, action)

    handler = getattr(bluetooth_cli, handler_name)
    assert handler(argparse.Namespace(address="AA:BB:CC:DD:EE:FF")) == 0
    action.assert_called_once_with("AA:BB:CC:DD:EE:FF")
