import argparse
import json

from .backlight_api import (
    BrightnessError,
    change_brightness,
    get_brightness,
    set_brightness,
)


def _get(arguments: argparse.Namespace) -> int:
    """Print the current display brightness in the requested format."""
    brightness = get_brightness()
    if arguments.json:
        print(json.dumps({"brightness": brightness}))
    else:
        print(brightness)
    return 0


def _set(arguments: argparse.Namespace) -> int:
    """Set the requested display brightness."""
    if not 0 <= arguments.percentage <= 100:
        raise BrightnessError(
            "Invalid brightness percentage. Only values between 0 and 100 are allowed."
        )

    set_brightness(arguments.percentage)
    return 0


def _change(arguments: argparse.Namespace) -> int:
    """Change the display brightness by the requested delta."""
    change_brightness(arguments.delta)
    return 0


# public API ---------------------------------------------------------------------------


def configure_brightness_parser(parser: argparse.ArgumentParser) -> None:
    """Configure the Brightness CLI commands.

    Parameters
    ----------
    `parser` : `argparse.ArgumentParser`
        Brightness parser of `desktopctl`.
    """
    commands = parser.add_subparsers(dest="brightness_command", required=True)

    # Query brightness.
    get_parser = commands.add_parser("get", help="Show the current brightness.")
    get_parser.add_argument(
        "--json", action="store_true", help="Output the current brightness as JSON."
    )
    get_parser.set_defaults(handler=_get)

    # Set brightness.
    set_parser = commands.add_parser("set", help="Set the brightness.")
    set_parser.add_argument(
        "percentage", type=int, help="Absolute display brightness percentage."
    )
    set_parser.set_defaults(handler=_set)

    # Change brightness.
    change_parser = commands.add_parser(
        "change", help="Increase or decrease the display brightness."
    )
    change_parser.add_argument(
        "delta", type=int, help="Relative change in percentage points."
    )
    change_parser.set_defaults(handler=_change)
