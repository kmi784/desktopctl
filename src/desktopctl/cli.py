import argparse
import logging
import sys

from desktopctl.wifi import (
    WifiError,
    connect_wifi_network,
    disconnect_wifi_network,
    enable_wifi,
    forget_wifi,
    list_saved_wifi_networks,
    list_visible_wifi_networks,
    scan_wifi_networks,
    wifi_is_enabled,
)

logger = logging.getLogger(__name__)


def _status_wifi(_arguments: argparse.Namespace) -> int:
    print("enabled" if wifi_is_enabled() else "disabled")
    return 0


def _list_visible_wifi(arguments: argparse.Namespace) -> int:
    for network in list_visible_wifi_networks():
        print(network)
    return 0


def _enable_wifi(arguments: argparse.Namespace) -> int:
    enable_wifi(True)
    return 0


def _disable_wifi(arguments: argparse.Namespace) -> int:
    enable_wifi(False)
    return 0


def _scan_wifi(arguments: argparse.Namespace) -> int:
    scan_wifi_networks()
    return 0


def _connect_wifi(arguments: argparse.Namespace) -> int:
    password: str | None = None

    if arguments.password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")

        if not password:
            raise WifiError("No WiFi password was provided on stdin.")

    connect_wifi_network(arguments.ssid, password)
    return 0


def _disconnect_wifi(arguments: argparse.Namespace) -> int:
    disconnect_wifi_network()
    return 0


def _list_saved_wifi(arguments: argparse.Namespace) -> int:
    for profile in list_saved_wifi_networks():
        print(profile)
    return 0


def _forget_wifi(arguments: argparse.Namespace) -> int:
    forget_wifi(arguments.uuid)
    return 0


def main() -> int:
    """Run the `desktopctl` CLI."""

    parser = argparse.ArgumentParser(
        prog="desktopctl", description="Control common Linux desktop functionality."
    )

    # Configure global options.
    parser.add_argument(
        "--debug", action="store_true", help="Enable diagnostic logging."
    )

    commands = parser.add_subparsers(dest="command", required=True)

    # Configure WiFi commands. ---------------------------------------------------------
    wifi_parser = commands.add_parser("wifi", help="Control WiFi functionality.")
    wifi_commands = wifi_parser.add_subparsers(
        dest="wifi_command",
        required=True,
    )

    # Query WiFi status.
    wifi_status_parser = wifi_commands.add_parser(
        "status", help="Show the current WiFi status."
    )
    wifi_status_parser.set_defaults(handler=_status_wifi)

    # List visible WiFi networks.
    wifi_visible_parser = wifi_commands.add_parser(
        "visible", help="List visible WiFi networks."
    )
    wifi_visible_parser.set_defaults(handler=_list_visible_wifi)

    # Set WiFi status.
    wifi_enable_parser = wifi_commands.add_parser("enable", help="Enable WiFi.")
    wifi_enable_parser.set_defaults(handler=_enable_wifi)
    wifi_disable_parser = wifi_commands.add_parser("disable", help="Disable WiFi.")
    wifi_disable_parser.set_defaults(handler=_disable_wifi)

    # Scan for WiFi networks.
    wifi_scan_parser = wifi_commands.add_parser("scan", help="Scan for WiFi networks.")
    wifi_scan_parser.set_defaults(handler=_scan_wifi)

    # Connect to a WiFi network.
    wifi_connect_parser = wifi_commands.add_parser(
        "connect", help="Connect to a WiFi network."
    )
    wifi_connect_parser.add_argument("ssid", help="SSID of the WiFi network.")
    wifi_connect_parser.add_argument(
        "--password-stdin",
        action="store_true",
        help="Read the WiFi password from stdin.",
    )
    wifi_connect_parser.set_defaults(handler=_connect_wifi)

    # Disconnect the active WiFi network.
    wifi_disconnect_parser = wifi_commands.add_parser(
        "disconnect", help="Disconnect the active WiFi network."
    )
    wifi_disconnect_parser.set_defaults(handler=_disconnect_wifi)

    # List saved WiFi networks.
    wifi_saved_parser = wifi_commands.add_parser(
        "saved", help="List saved WiFi networks."
    )
    wifi_saved_parser.set_defaults(handler=_list_saved_wifi)

    # Delete a saved WiFi connection profile.
    wifi_forget_parser = wifi_commands.add_parser(
        "forget", help="Delete a saved WiFi connection profile."
    )
    wifi_forget_parser.add_argument(
        "uuid", help="UUID of the saved WiFi connection profile."
    )
    wifi_forget_parser.set_defaults(handler=_forget_wifi)

    # Parse arguments and dispatch the selected command.
    arguments = parser.parse_args()

    if arguments.debug:
        from desktopctl.logging_config import configure_logging

        configure_logging({"desktopctl": logging.DEBUG})

    try:
        return arguments.handler(arguments)
    except WifiError as error:
        print(f"desktopctl: {error}", file=sys.stderr)
        return 1
