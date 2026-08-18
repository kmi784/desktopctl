import argparse
import json

from ..misc import print_table
from .upower_api import (
    PowerProfile,
    device_is_ac_connected,
    get_battery_status,
    get_power_profile,
    set_power_profile,
)


def _status(arguments: argparse.Namespace) -> int:
    """Print the power status in the requested format."""
    status = get_battery_status()
    data: dict[str, object] = {
        "battery": status.percentage,
        "charging": status.charging,
        "connected": device_is_ac_connected(),
        "profile": get_power_profile().value,
    }

    if arguments.json:
        print(json.dumps(data))
    else:
        print_table([data])
    return 0


def _profile(arguments: argparse.Namespace) -> int:
    """Set the requested power profile."""
    set_power_profile(arguments.profile)
    return 0


# public API ---------------------------------------------------------------------------


def configure_power_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the Power CLI commands.

    Parameters
    ----------
    `parser` : `argparse.ArgumentParser`
        Power parser of `desktopctl`.
    """
    commands = parser.add_subparsers(dest="power_command", required=True)

    # Query power status.
    status_parser = commands.add_parser("status", help="Show the current power status.")
    status_parser.add_argument(
        "--json", action="store_true", help="Output the power status as JSON."
    )
    status_parser.set_defaults(handler=_status)

    # Set power profile.
    profile_parser = commands.add_parser("profile", help="Set power profile.")
    profile_parser.add_argument(
        "profile",
        type=PowerProfile,
        choices=PowerProfile,
        help="Power profile to activate.",
    )
    profile_parser.set_defaults(handler=_profile)
