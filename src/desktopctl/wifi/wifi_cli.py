import argparse
import json
import sys

from .nmcli_api import (
    WifiError,
    connect_wifi_network,
    disconnect_wifi_network,
    enable_wifi,
    forget_wifi,
    list_saved_wifi_networks,
    list_visible_wifi_networks,
    scan_wifi_networks,
    show_connected_wifi,
    wifi_is_enabled,
)


def _print_table(data: list[dict]) -> None:
    """Print dictionary records as a table."""
    if not data:
        return

    columns = list(data[0])
    rows = [
        {
            key: str(value).lower() if isinstance(value, bool) else str(value)
            for key, value in row.items()
        }
        for row in data
    ]
    widths = {
        column: max(len(column), *(len(row[column]) for row in rows))
        for column in columns
    }

    def _print_row(row: dict[str, str]) -> None:
        print(
            "  ".join(f"{row[column]:<{widths[column]}}" for column in columns).rstrip()
        )

    _print_row({column: column.upper() for column in columns})

    for row in rows:
        _print_row(row)


# listings


def _status(arguments: argparse.Namespace) -> int:
    """Print the WiFi status in the requested format."""
    enabled = wifi_is_enabled()
    network = show_connected_wifi() if enabled else None

    if arguments.json:
        data = {
            "enabled": enabled,
            "connected": network is not None,
            "ssid": network.ssid if network else None,
            "signal": network.signal if network else None,
            "security": network.security if network else None,
        }
        print(json.dumps(data))
    else:
        print("enabled" if enabled else "disabled")

    return 0


def _list_visible(arguments: argparse.Namespace) -> int:
    """Print visible WiFi networks in the requested format."""
    data = [
        {
            "ssid": network.ssid,
            "signal": network.signal,
            "security": network.security,
            "connected": network.connected,
        }
        for network in list_visible_wifi_networks()
    ]

    if arguments.json:
        print(json.dumps(data))
    else:
        _print_table(data)
    return 0


def _list_saved(arguments: argparse.Namespace) -> int:
    """Print saved WiFi profiles in the requested format."""
    data = [
        {
            "ssid": profile.ssid,
            "name": profile.profile_name,
            "uuid": profile.uuid,
        }
        for profile in list_saved_wifi_networks()
    ]

    if arguments.json:
        print(json.dumps(data))
    else:
        _print_table(data)

    return 0


# control


def _enable(_arguments: argparse.Namespace) -> int:
    """Enable WiFi."""
    enable_wifi(True)
    return 0


def _disable(_arguments: argparse.Namespace) -> int:
    """Disable WiFi."""
    enable_wifi(False)
    return 0


def _scan(_arguments: argparse.Namespace) -> int:
    """Request a WiFi scan."""
    scan_wifi_networks()
    return 0


def _connect(arguments: argparse.Namespace) -> int:
    """Connect to a WiFi network."""
    password: str | None = None

    if arguments.password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")

        if not password:
            raise WifiError("No WiFi password was provided on stdin.")

    connect_wifi_network(arguments.ssid, password)
    return 0


def _disconnect(_arguments: argparse.Namespace) -> int:
    """Disconnect the active WiFi network."""
    disconnect_wifi_network()
    return 0


def _forget(arguments: argparse.Namespace) -> int:
    """Delete a saved WiFi profile."""
    forget_wifi(arguments.uuid)
    return 0


# public API ---------------------------------------------------------------------------


def configure_wifi_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the WiFi CLI commands.

    Parameters
    ----------
    `parser` : `argparse.ArgumentParser`
        WiFi parser of `desktopctl`
    """
    wifi_commands = parser.add_subparsers(
        dest="wifi_command",
        required=True,
    )

    # Query WiFi status.
    status_parser = wifi_commands.add_parser(
        "status", help="Show the current WiFi status."
    )
    status_parser.add_argument(
        "--json", action="store_true", help="Output the WiFi status as JSON."
    )
    status_parser.set_defaults(handler=_status)

    # List visible WiFi networks.
    visible_parser = wifi_commands.add_parser(
        "visible", help="List visible WiFi networks."
    )
    visible_parser.add_argument(
        "--json", action="store_true", help="Output all visible WiFi networks as JSON."
    )
    visible_parser.set_defaults(handler=_list_visible)

    # List saved WiFi networks.
    saved_parser = wifi_commands.add_parser("saved", help="List saved WiFi networks.")
    saved_parser.add_argument(
        "--json", action="store_true", help="Output all saved WiFi networks as JSON."
    )
    saved_parser.set_defaults(handler=_list_saved)

    # Set WiFi status.
    enable_parser = wifi_commands.add_parser("enable", help="Enable WiFi.")
    enable_parser.set_defaults(handler=_enable)
    disable_parser = wifi_commands.add_parser("disable", help="Disable WiFi.")
    disable_parser.set_defaults(handler=_disable)

    # Scan for WiFi networks.
    scan_parser = wifi_commands.add_parser("scan", help="Scan for WiFi networks.")
    scan_parser.set_defaults(handler=_scan)

    # Connect to a WiFi network.
    connect_parser = wifi_commands.add_parser(
        "connect", help="Connect to a WiFi network."
    )
    connect_parser.add_argument("ssid", help="SSID of the WiFi network.")
    connect_parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read the WiFi password from stdin.",
    )
    connect_parser.set_defaults(handler=_connect)

    # Disconnect the active WiFi network.
    disconnect_parser = wifi_commands.add_parser(
        "disconnect", help="Disconnect the active WiFi network."
    )
    disconnect_parser.set_defaults(handler=_disconnect)

    # Delete a saved WiFi connection profile.
    forget_parser = wifi_commands.add_parser(
        "forget", help="Delete a saved WiFi connection profile."
    )
    forget_parser.add_argument("uuid", help="UUID of the saved WiFi connection profile.")
    forget_parser.set_defaults(handler=_forget)
