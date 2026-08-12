import argparse

from desktopctl.wifi import _wifi_list, _wifi_status


def main() -> int:
    """Entry point for the cli of `desktopctl`"""

    parser = argparse.ArgumentParser(
        prog="desktopctl", description="Control common Linux desktop functionality."
    )

    commands = parser.add_subparsers(dest="command", required=True)

    # wifi
    wifi_parser = commands.add_parser("wifi", help="Control wifi functionality.")
    wifi_commands = wifi_parser.add_subparsers(
        dest="wifi_command",
        required=True,
    )
    status_parser = wifi_commands.add_parser(
        "status", help="Show the current wifi status."
    )
    status_parser.set_defaults(handler=_wifi_status)

    list_parser = wifi_commands.add_parser("list", help="List avaiable wifi networks.")
    list_parser.set_defaults(handler=_wifi_list)

    # coming soon
    commands.add_parser("bluetooth", help="Control bluetooth functionality.")
    commands.add_parser("audio", help="Control audio functionality.")
    commands.add_parser("brightness", help="Control brightness functionality.")
    commands.add_parser("energy", help="Control energy profile.")

    # run command
    arguments = parser.parse_args()
    return arguments.handler(arguments)
