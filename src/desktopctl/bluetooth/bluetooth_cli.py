import argparse

# listings


def _status(arguments: argparse.Namespace) -> int:
    """Print the Bluetooth status in the requested format."""
    if arguments.json:
        print("Status as JSON")
    else:
        print("Status")

    return 0


def _list_visible(arguments: argparse.Namespace) -> int:
    """Print visible Bluetooth devices in the requested format."""
    if arguments.json:
        print("List visible Bluetooth devices as JSON")
    else:
        print("List visible Bluetooth devices")

    return 0


def _list_paired(arguments: argparse.Namespace) -> int:
    """Print paired Bluetooth devices in the requested format."""
    if arguments.json:
        print("List paired Bluetooth devices as JSON")
    else:
        print("List paired Bluetooth devices")

    return 0


# control


def _enable(_arguments: argparse.Namespace) -> int:
    """Enable Bluetooth."""
    return 0


def _disable(_arguments: argparse.Namespace) -> int:
    """Disable Bluetooth."""
    return 0


def _scan(_arguments: argparse.Namespace) -> int:
    """Request a Bluetooth scan."""
    return 0


def _pair(arguments: argparse.Namespace) -> int:
    """Pair a Bluetooth device."""
    return 0


def _connect(arguments: argparse.Namespace) -> int:
    """Connect a paired Bluetooth device."""
    return 0


def _disconnect(arguments: argparse.Namespace) -> int:
    """Disconnect a connected Bluetooth device."""
    return 0


def _forget(arguments: argparse.Namespace) -> int:
    """Forget a paired Bluetooth device."""
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
