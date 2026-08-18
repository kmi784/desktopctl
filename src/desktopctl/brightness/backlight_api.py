import logging
from pathlib import Path

import dbus

from ..misc import translate_dbus_errors

logger = logging.getLogger(__name__)


BACKLIGHT_ROOT = Path("/sys/class/backlight")

LOGIN1_SERVICE = "org.freedesktop.login1"
LOGIN1_SESSION_PATH = "/org/freedesktop/login1/session/auto"
LOGIN1_SESSION_INTERFACE = "org.freedesktop.login1.Session"


def _get_backlight_device() -> Path:
    """Return the available backlight device."""
    try:
        devices = list(BACKLIGHT_ROOT.iterdir())
    except OSError as error:
        raise BrightnessError(f"Failed to list backlight devices: {error}") from error
    if not devices:
        raise BrightnessError("No backlight device found.")
    if len(devices) > 1:
        raise BrightnessError("Multiple backlight devices found.")
    return devices[0]


def _read_integer(attribute_path: Path) -> int:
    """Read an integer from a sysfs attribute."""
    try:
        return int(attribute_path.read_text().strip())
    except (OSError, ValueError) as error:
        raise BrightnessError(
            f"Failed to read backlight attribute {attribute_path!r}."
        ) from error


# public API ---------------------------------------------------------------------------


class BrightnessError(RuntimeError):
    """
    Indicate that a brightness operation failed.

    Parameters
    ----------
    `message` : `str`
        Description of the failed brightness operation.
    """


def get_brightness() -> int:
    """Return the current display brightness.

    Returns
    -------
    `int`
        Current display brightness as a percentage.
    """
    logger.debug("Query display brightness via sysfs.")
    device_path = _get_backlight_device()
    brightness = _read_integer(device_path / "brightness")
    max_brightness = _read_integer(device_path / "max_brightness")

    if max_brightness <= 0:
        raise BrightnessError("Invalid maximum backlight brightness.")

    return round(brightness / max_brightness * 100)


@translate_dbus_errors(BrightnessError)
def set_brightness(percentage: int) -> None:
    """Set the display brightness.

    Parameters
    ----------
    `percentage` : `int`
        Absolute display brightness percentage.
    """
    logger.debug("Set display brightness to %d%% via systemd-logind D-Bus.", percentage)
    bus = dbus.SystemBus()
    login1_proxy = bus.get_object(LOGIN1_SERVICE, LOGIN1_SESSION_PATH)
    session = dbus.Interface(login1_proxy, LOGIN1_SESSION_INTERFACE)

    device_path = _get_backlight_device()

    max_brightness = _read_integer(device_path / "max_brightness")
    if max_brightness <= 0:
        raise BrightnessError("Invalid maximum backlight brightness.")

    value = round(max_brightness * percentage / 100)
    session.SetBrightness("backlight", device_path.name, dbus.UInt32(value))


def change_brightness(delta: int) -> None:
    """Change the display brightness.

    Parameters
    ----------
    `delta` : `int`
        Relative change in percentage points.
    """
    logger.debug("Change display brightness by %+d percentage points.", delta)
    current_brightness = get_brightness()
    set_brightness(max(0, min(current_brightness + delta, 100)))
