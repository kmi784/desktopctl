from unittest.mock import Mock

import dbus
import pytest

from desktopctl.bluetooth.bluez_agent import AgentRejected, BlueZAgent

DEVICE_PATH = "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"
OTHER_DEVICE_PATH = "/org/bluez/hci0/dev_11_22_33_44_55_66"


@pytest.fixture
def bluez_agent():
    bus = Mock()
    agent = BlueZAgent(bus, DEVICE_PATH)
    yield agent
    agent.remove_from_connection()


@pytest.mark.parametrize(
    ("method_name", "arguments"),
    [
        ("RequestConfirmation", (dbus.UInt32(123456),)),
        ("RequestAuthorization", ()),
        ("AuthorizeService", (dbus.String("0000110b-0000-1000-8000-00805f9b34fb"),)),
    ],
    ids=["confirmation", "authorization", "service"],
)
def test_agent_authorizes_selected_device(bluez_agent, method_name, arguments):
    method = getattr(bluez_agent, method_name)

    assert method(dbus.ObjectPath(DEVICE_PATH), *arguments) is None


@pytest.mark.parametrize(
    ("method_name", "arguments"),
    [
        ("RequestConfirmation", (dbus.UInt32(123456),)),
        ("RequestAuthorization", ()),
        ("AuthorizeService", (dbus.String("0000110b-0000-1000-8000-00805f9b34fb"),)),
    ],
    ids=["confirmation", "authorization", "service"],
)
def test_agent_rejects_other_device(bluez_agent, method_name, arguments):
    method = getattr(bluez_agent, method_name)

    with pytest.raises(AgentRejected, match="Unexpected Bluetooth device"):
        method(dbus.ObjectPath(OTHER_DEVICE_PATH), *arguments)


@pytest.mark.parametrize(
    ("method_name", "arguments"),
    [
        ("RequestPinCode", ()),
        ("DisplayPinCode", (dbus.String("123456"),)),
        ("RequestPasskey", ()),
        ("DisplayPasskey", (dbus.UInt32(123456), dbus.UInt16(0))),
    ],
    ids=["request-pin", "display-pin", "request-passkey", "display-passkey"],
)
def test_agent_rejects_interactive_pairing(bluez_agent, method_name, arguments):
    method = getattr(bluez_agent, method_name)

    with pytest.raises(AgentRejected, match="requires"):
        method(dbus.ObjectPath(DEVICE_PATH), *arguments)


def test_agent_handles_release_and_cancel(bluez_agent):
    assert bluez_agent.Release() is None
    assert bluez_agent.Cancel() is None
