import argparse
import json

from ..misc import print_table
from .bluez_api import (
    BluetoothDevice,
    bluetooth_is_enabled,
    connect_bluetooth_device,
    disconnect_bluetooth_device,
    enable_bluetooth,
    forget_bluetooth_device,
    list_connected_bluetooth_devices,
    list_paired_bluetooth_devices,
    list_visible_bluetooth_devices,
    pair_bluetooth_device,
    scan_bluetooth_devices,
)


def _device_to_dict(device: BluetoothDevice) -> dict[str, object]:
    return {
        "address": device.address,
        "name": device.name,
        "rssi": device.rssi,
        "battery": device.battery,
        "paired": device.paired,
        "connected": device.connected,
    }


# listings


def _status(arguments: argparse.Namespace) -> int:
    """Print the Bluetooth status in the requested format."""
    enabled = bluetooth_is_enabled()

    if arguments.json:
        data = {
            "enabled": enabled,
            "connected_devices": [
                _device_to_dict(device) for device in list_connected_bluetooth_devices()
            ],
        }

        print(json.dumps(data))
    else:
        print("enabled" if enabled else "disabled")

    return 0


def _list_visible(arguments: argparse.Namespace) -> int:
    """Print visible Bluetooth devices in the requested format."""
    data = [_device_to_dict(device) for device in list_visible_bluetooth_devices()]
    if arguments.json:
        print(json.dumps(data))
    else:
        print_table(data)

    return 0


def _list_paired(arguments: argparse.Namespace) -> int:
    """Print paired Bluetooth devices in the requested format."""
    data = [_device_to_dict(device) for device in list_paired_bluetooth_devices()]
    if arguments.json:
        print(json.dumps(data))
    else:
        print_table(data)

    return 0


# control


def _enable(_arguments: argparse.Namespace) -> int:
    """Enable Bluetooth."""
    enable_bluetooth(True)
    return 0


def _disable(_arguments: argparse.Namespace) -> int:
    """Disable Bluetooth."""
    enable_bluetooth(False)
    return 0


def _scan(_arguments: argparse.Namespace) -> int:
    """Request a Bluetooth scan."""
    scan_bluetooth_devices()
    return 0


def _pair(arguments: argparse.Namespace) -> int:
    """Pair a Bluetooth device."""
    pair_bluetooth_device(arguments.address)
    return 0


def _connect(arguments: argparse.Namespace) -> int:
    """Connect a paired Bluetooth device."""
    connect_bluetooth_device(arguments.address)
    return 0


def _disconnect(arguments: argparse.Namespace) -> int:
    """Disconnect a connected Bluetooth device."""
    disconnect_bluetooth_device(arguments.address)
    return 0


def _forget(arguments: argparse.Namespace) -> int:
    """Forget a paired Bluetooth device."""
    forget_bluetooth_device(arguments.address)
    return 0


# public API ---------------------------------------------------------------------------


def configure_bluetooth_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the Bluetooth CLI commands.

    Parameters
    ----------
    `parser` : `argparse.ArgumentParser`
        Bluetooth parser for `desktopctl`.
    """
    commands = parser.add_subparsers(dest="bluetooth_command", required=True)

    # Query Bluetooth status.
    status_parser = commands.add_parser(
        "status", help="Show the current Bluetooth status."
    )
    status_parser.add_argument(
        "--json", action="store_true", help="Output the Bluetooth status as JSON."
    )
    status_parser.set_defaults(handler=_status)

    # List visible Bluetooth devices.
    visible_parser = commands.add_parser(
        "visible", help="List visible Bluetooth devices."
    )
    visible_parser.add_argument(
        "--json",
        action="store_true",
        help="Output all visible Bluetooth devices as JSON.",
    )
    visible_parser.set_defaults(handler=_list_visible)

    # List paired Bluetooth devices.
    paired_parser = commands.add_parser(
        "paired", help="List all paired Bluetooth devices."
    )
    paired_parser.add_argument(
        "--json",
        action="store_true",
        help="Output all paired Bluetooth devices as JSON.",
    )
    paired_parser.set_defaults(handler=_list_paired)

    # Set Bluetooth status.
    enable_parser = commands.add_parser("enable", help="Enable Bluetooth.")
    enable_parser.set_defaults(handler=_enable)
    disable_parser = commands.add_parser("disable", help="Disable Bluetooth.")
    disable_parser.set_defaults(handler=_disable)

    # Scan for Bluetooth devices.
    scan_parser = commands.add_parser("scan", help="Scan for Bluetooth devices.")
    scan_parser.set_defaults(handler=_scan)

    # Pair a Bluetooth device.
    pair_parser = commands.add_parser("pair", help="Pair a Bluetooth device.")
    pair_parser.add_argument("address", help="Bluetooth device address.")
    pair_parser.set_defaults(handler=_pair)

    # Connect a Bluetooth device.
    connect_parser = commands.add_parser(
        "connect", help="Connect a paired Bluetooth device."
    )
    connect_parser.add_argument("address", help="Bluetooth device address.")
    connect_parser.set_defaults(handler=_connect)

    # Disconnect a Bluetooth device.
    disconnect_parser = commands.add_parser(
        "disconnect", help="Disconnect a connected Bluetooth device."
    )
    disconnect_parser.add_argument("address", help="Bluetooth device address.")
    disconnect_parser.set_defaults(handler=_disconnect)

    # Forget a paired Bluetooth device.
    forget_parser = commands.add_parser(
        "forget", help="Forget a paired Bluetooth device."
    )
    forget_parser.add_argument("address", help="Bluetooth device address.")
    forget_parser.set_defaults(handler=_forget)
