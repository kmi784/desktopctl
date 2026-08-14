import logging
from dataclasses import dataclass
from subprocess import CalledProcessError, run

logger = logging.getLogger(__name__)


WIFI_IEEE = "802-11-wireless"


def _run_nmcli(*args: str, input_text: str | None = None) -> str:
    """Run `nmcli` and return its standard output.

    Parameters
    ----------
    `*args` : `str`
        Arguments, options, and commands passed to `nmcli`.
    `input_text` : `str` or `None`, optional
        Text passed to `nmcli` through standard input.

    Returns
    -------
    `str`
        Standard output of the `nmcli` command with surrounding whitespace removed.
    """
    logger.debug("Run nmcli with %s.", args)

    try:
        result = run(
            ["nmcli", *args],
            check=True,
            capture_output=True,
            text=True,
            input=input_text,
        )
    except FileNotFoundError as error:
        raise WifiError("nmcli is not installed.") from error
    except CalledProcessError as error:
        msg = error.stderr.strip() or "nmcli command failed."
        raise WifiError(msg) from error

    return result.stdout.strip()


def _get_connected_wifi_device() -> str | None:
    """Return the connected WiFi device.

    Returns
    -------
    `str` or `None`
        Name of the connected WiFi device, or `None` if no device is connected.
    """
    logger.debug("Run nmcli to query connected WiFi device.")

    output = _run_nmcli(
        "--terse",
        "--escape",
        "no",
        "--fields",
        "DEVICE,TYPE,STATE",
        "device",
        "status",
    )

    for line in output.splitlines():
        device, device_type, state = line.split(":", maxsplit=2)

        if device_type == "wifi" and state == "connected":
            return device

    return None


# public API ---------------------------------------------------------------------------


class WifiError(RuntimeError):
    """Indicate that a WiFi operation failed."""


@dataclass(frozen=True, slots=True)  # creates an immutable datatype
class WifiNetwork:
    """Represent a visible WiFi network.

    Parameters
    ----------
    `ssid` : `str`
        Network name.
    `signal` : `int`
        Signal strength from 0 to 100.
    `security` : `str`
        Security reported by NetworkManager.
    `connected` : `bool`
        Whether this network is currently connected.
    """

    ssid: str
    signal: int
    security: str
    connected: bool


@dataclass(frozen=True, slots=True)  # creates an immutable datatype
class SavedWifiProfile:
    """Represent a saved NetworkManager WiFi profile.

    Parameters
    ----------
    `uuid` : `str`
        Unique identifier of the NetworkManager connection profile.
    `profile_name` : `str`
        Human-readable name of the connection profile.
    `ssid` : `str`
        SSID associated with the connection profile.
    """

    uuid: str
    profile_name: str
    ssid: str


def wifi_is_enabled() -> bool:
    """Return whether WiFi is enabled.

    Returns
    -------
    `bool`
        `True` if WiFi is enabled; otherwise, `False`.
    """
    logger.info("Call nmcli to query WiFi status.")

    return _run_nmcli("radio", "wifi") == "enabled"


def enable_wifi(enable: bool) -> None:
    """Enable or disable WiFi.

    Parameters
    ----------
    `enable` : `bool`
        Whether to enable (`True`) or disable (`False`) WiFi.
    """
    logger.info("Call nmcli to set WiFi status.")

    _run_nmcli("radio", "wifi", "on" if enable else "off")


def list_visible_wifi_networks() -> list[WifiNetwork]:
    """List all visible WiFi networks.

    Returns
    -------
    `list[WifiNetwork]`
        Visible WiFi networks reported by NetworkManager.
    """
    logger.info("Call nmcli to list all visible WiFi networks.")

    output = _run_nmcli(
        "--terse",
        "--escape",
        "no",
        "--fields",
        "SIGNAL,SECURITY,IN-USE,SSID",
        "device",
        "wifi",
        "list",
        "--rescan",
        "no",
    )

    networks = []
    for line in output.splitlines():
        signal, security, in_use, ssid = line.split(":", maxsplit=3)

        if not ssid:
            continue

        networks.append(WifiNetwork(ssid, int(signal), security, in_use == "*"))

    return networks


def scan_wifi_networks() -> None:
    """Scan for visible WiFi networks."""
    logger.info("Call nmcli to scan for visible WiFi networks.")

    _run_nmcli("device", "wifi", "rescan")


def connect_wifi_network(ssid: str, password: str | None = None) -> None:
    """Connect to a WiFi network.

    Parameters
    ----------
    `ssid` : `str`
        SSID of the WiFi network.
    `password` : `str` or `None`, optional
        Password of the WiFi network, or `None` to use stored credentials.
    """
    logger.info("Call nmcli to connect to WiFi network %r.", ssid)

    if password is None:
        _run_nmcli("device", "wifi", "connect", ssid)
        return

    _run_nmcli("--ask", "device", "wifi", "connect", ssid, input_text=f"{password}\n")


def disconnect_wifi_network() -> None:
    """Disconnect the active WiFi network."""
    logger.info("Call nmcli to disconnect the active WiFi network.")

    device = _get_connected_wifi_device()

    if device is None:
        raise WifiError("No active WiFi connection was found.")

    _run_nmcli("device", "disconnect", device)


def list_saved_wifi_networks() -> list[SavedWifiProfile]:
    """List saved NetworkManager WiFi profiles.

    Returns
    -------
    `list[SavedWifiProfile]`
        Saved NetworkManager WiFi profiles.
    """
    logger.info("Call nmcli to list saved WiFi profiles.")

    output = _run_nmcli(
        "--terse",
        "--escape",
        "no",
        "--fields",
        "UUID,TYPE,NAME",
        "connection",
        "show",
    )

    profiles = []

    for line in output.splitlines():
        uuid, connection_type, profile_name = line.split(":", maxsplit=2)

        if connection_type != WIFI_IEEE:
            continue

        ssid = _run_nmcli(
            "--escape",
            "no",
            "--get-values",
            WIFI_IEEE + ".ssid",
            "connection",
            "show",
            "uuid",
            uuid,
        )

        profiles.append(SavedWifiProfile(uuid, profile_name, ssid))

    return profiles


def forget_wifi(uuid: str) -> None:
    """Delete a saved WiFi connection profile.

    Parameters
    ----------
    `uuid` : `str`
        Unique identifier of the NetworkManager connection profile.
    """
    logger.info("Call nmcli to delete WiFi connection profile %r.", uuid)

    _run_nmcli("connection", "delete", "uuid", uuid)
