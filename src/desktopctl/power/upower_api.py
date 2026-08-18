import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

import dbus

from ..misc import translate_dbus_errors

logger = logging.getLogger(__name__)

UPOWER_SERVICE = "org.freedesktop.UPower"
UPOWER_PATH = "/org/freedesktop/UPower"
UPOWER_DEVICE_PATH = "/org/freedesktop/UPower/devices/DisplayDevice"
UPOWER_DEVICE_INTERFACE = "org.freedesktop.UPower.Device"

POWER_PROFILE_SERVICE = "org.freedesktop.UPower.PowerProfiles"
POWER_PROFILE_PATH = "/org/freedesktop/UPower/PowerProfiles"


def _display_device_properties() -> dict[str, Any]:
    """Return all properties of the UPower display device."""
    bus = dbus.SystemBus()
    upower_proxy = bus.get_object(UPOWER_SERVICE, UPOWER_DEVICE_PATH)
    properties = dbus.Interface(upower_proxy, dbus.PROPERTIES_IFACE)
    return properties.GetAll(UPOWER_DEVICE_INTERFACE)


def _power_profile_properties_interface() -> dbus.Interface:
    """Return the Power Profiles properties interface."""
    bus = dbus.SystemBus()
    power_profile_proxy = bus.get_object(POWER_PROFILE_SERVICE, POWER_PROFILE_PATH)
    return dbus.Interface(power_profile_proxy, dbus.PROPERTIES_IFACE)


# public API ---------------------------------------------------------------------------


class PowerProfile(StrEnum):
    """
    Represent a supported system power profile.

    Parameters
    ----------
    `value` : `str`
        D-Bus value identifying the power profile.
    """

    POWER_SAVER = "power-saver"
    BALANCED = "balanced"
    PERFORMANCE = "performance"


class PowerError(RuntimeError):
    """
    Indicate that a power operation failed.

    Parameters
    ----------
    `message` : `str`
        Description of the failed power operation.
    """


@dataclass(frozen=True, slots=True)
class BatteryStatus:
    """
    Represent the current battery status.

    Parameters
    ----------
    `percentage` : `int | None`
        Current battery percentage or `None` when no battery is
        present.
    `charging` : `bool | None`
        Whether the battery is charging or `None` when no battery
        is present.
    """

    percentage: int | None
    charging: bool | None


@translate_dbus_errors(PowerError)
def get_battery_status() -> BatteryStatus:
    """Return the current battery status.

    Returns
    -------
    `BatteryStatus`
        Current battery percentage and charging state.
    """
    values = _display_device_properties()
    if not bool(values["IsPresent"]):
        return BatteryStatus(None, None)

    return BatteryStatus(
        round(float(values["Percentage"])),
        int(values["State"]) == 1,
    )


@translate_dbus_errors(PowerError)
def device_is_ac_connected() -> bool:
    """Return whether the system is connected to external power.

    Returns
    -------
    `bool`
        `True` if the system is not running on battery; otherwise, `False`.
    """
    bus = dbus.SystemBus()
    upower_proxy = bus.get_object(UPOWER_SERVICE, UPOWER_PATH)
    properties = dbus.Interface(upower_proxy, dbus.PROPERTIES_IFACE)
    value = properties.Get(UPOWER_SERVICE, "OnBattery")
    return not bool(value)


@translate_dbus_errors(PowerError)
def get_power_profile() -> PowerProfile:
    """Return the currently active power profile.

    Returns
    -------
    `PowerProfile`
        Currently active power profile.

    Raises
    ------
    `PowerError`
        If the active profile reported by the service is unsupported.
    """
    properties = _power_profile_properties_interface()
    value = properties.Get(POWER_PROFILE_SERVICE, "ActiveProfile")

    try:
        return PowerProfile(str(value))
    except ValueError as error:
        raise PowerError(f"Unsupported power profile reported: {value!r}") from error


@translate_dbus_errors(PowerError)
def set_power_profile(profile: PowerProfile) -> None:
    """Set the active power profile.

    Parameters
    ----------
    `profile` : `PowerProfile`
        Power profile to activate.
    """
    properties = _power_profile_properties_interface()
    properties.Set(POWER_PROFILE_SERVICE, "ActiveProfile", dbus.String(profile.value))
