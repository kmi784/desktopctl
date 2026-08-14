import argparse
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
    wifi_is_enabled,
)

# listings


def _status(_arguments: argparse.Namespace) -> int:
    print("enabled" if wifi_is_enabled() else "disabled")
    return 0


def _list_visible(_arguments: argparse.Namespace) -> int:
    for network in list_visible_wifi_networks():
        print(network)
    return 0


def _list_saved(_arguments: argparse.Namespace) -> int:
    for profile in list_saved_wifi_networks():
        print(profile)
    return 0


# control


def _enable(_arguments: argparse.Namespace) -> int:
    enable_wifi(True)
    return 0


def _disable(_arguments: argparse.Namespace) -> int:
    enable_wifi(False)
    return 0


def _scan(_arguments: argparse.Namespace) -> int:
    scan_wifi_networks()
    return 0


def _connect(arguments: argparse.Namespace) -> int:
    password: str | None = None

    if arguments.password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")

        if not password:
            raise WifiError("No WiFi password was provided on stdin.")

    connect_wifi_network(arguments.ssid, password)
    return 0


def _disconnect(_arguments: argparse.Namespace) -> int:
    disconnect_wifi_network()
    return 0


def _forget(arguments: argparse.Namespace) -> int:
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
    status_parser.set_defaults(handler=_status)

    # List visible WiFi networks.
    visible_parser = wifi_commands.add_parser(
        "visible", help="List visible WiFi networks."
    )
    visible_parser.set_defaults(handler=_list_visible)

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

    # List saved WiFi networks.
    saved_parser = wifi_commands.add_parser("saved", help="List saved WiFi networks.")
    saved_parser.set_defaults(handler=_list_saved)

    # Delete a saved WiFi connection profile.
    forget_parser = wifi_commands.add_parser(
        "forget", help="Delete a saved WiFi connection profile."
    )
    forget_parser.add_argument("uuid", help="UUID of the saved WiFi connection profile.")
    forget_parser.set_defaults(handler=_forget)
