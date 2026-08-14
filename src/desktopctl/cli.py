import argparse
import logging
import sys

from desktopctl.wifi import WifiError, configure_wifi_parser

logger = logging.getLogger(__name__)


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

    # Add WiFi commands
    wifi_parser = commands.add_parser("wifi", help="Control WiFi functionality.")
    configure_wifi_parser(wifi_parser)

    # Parse arguments and dispatch the selected command.
    arguments = parser.parse_args()

    if arguments.debug:
        from desktopctl.logging_config import configure_logging

        configure_logging({"desktopctl": logging.DEBUG})

    try:
        return arguments.handler(arguments)
    except WifiError as error:
        logger.debug("WiFi command failed.", exc_info=True)
        print(f"desktopctl: {error}", file=sys.stderr)
        return 1
