import logging

import dbus
import dbus.service

logger = logging.getLogger(__name__)


BLUEZ_AGENT_CAPABILITY = "NoInputNoOutput"
BLUEZ_AGENT_INTERFACE = "org.bluez.Agent1"
BLUEZ_AGENT_MANAGER_INTERFACE = "org.bluez.AgentManager1"
BLUEZ_AGENT_MANAGER_PATH = "/org/bluez"
BLUEZ_AGENT_PATH = "/org/desktopctl/bluez_agent"


class AgentRejected(dbus.DBusException):
    """Indicate that the BlueZ agent rejected an authentication request.

    Parameters
    ----------
    `message` : `str`
        Reason for rejecting the authentication request.
    """

    _dbus_error_name = "org.bluez.Error.Rejected"


class BlueZAgent(dbus.service.Object):
    """Authorize non-interactive pairing for one Bluetooth device.

    The agent supports BlueZ's `NoInputNoOutput` capability and therefore only
    handles pairing methods that require no PIN or passkey interaction. Requests
    concerning any device other than the explicitly selected device are rejected.

    Parameters
    ----------
    `connection` : `dbus.bus.BusConnection`
        D-Bus connection used for the pairing request.
    `device_path` : `str`
        BlueZ object path of the device authorized for pairing.
    """

    def __init__(
        self,
        connection: dbus.bus.BusConnection,
        device_path: str,
    ) -> None:
        super().__init__(connection, BLUEZ_AGENT_PATH)
        self._device_path = device_path

    def _authorize_device(self, device: dbus.ObjectPath) -> None:
        """Reject requests concerning a different Bluetooth device."""
        if str(device) != self._device_path:
            raise AgentRejected("Unexpected Bluetooth device.")

    @dbus.service.method(BLUEZ_AGENT_INTERFACE, in_signature="", out_signature="")
    def Release(self) -> None:
        """Handle release of the agent by BlueZ."""
        logger.debug("BlueZ released the Bluetooth pairing agent.")

    @dbus.service.method(BLUEZ_AGENT_INTERFACE, in_signature="o", out_signature="s")
    def RequestPinCode(self, device: dbus.ObjectPath) -> str:
        """Reject pairing that requires PIN input."""
        self._authorize_device(device)
        raise AgentRejected("Bluetooth pairing requires PIN input.")

    @dbus.service.method(BLUEZ_AGENT_INTERFACE, in_signature="os", out_signature="")
    def DisplayPinCode(self, device: dbus.ObjectPath, pincode: str) -> None:
        """Reject pairing that requires displaying a PIN."""
        self._authorize_device(device)
        raise AgentRejected("Bluetooth pairing requires displaying a PIN.")

    @dbus.service.method(BLUEZ_AGENT_INTERFACE, in_signature="o", out_signature="u")
    def RequestPasskey(self, device: dbus.ObjectPath) -> int:
        """Reject pairing that requires passkey input."""
        self._authorize_device(device)
        raise AgentRejected("Bluetooth pairing requires passkey input.")

    @dbus.service.method(
        BLUEZ_AGENT_INTERFACE,
        in_signature="ouq",
        out_signature="",
    )
    def DisplayPasskey(
        self,
        device: dbus.ObjectPath,
        passkey: int,
        entered: int,
    ) -> None:
        """Reject pairing that requires displaying a passkey."""
        self._authorize_device(device)
        raise AgentRejected("Bluetooth pairing requires displaying a passkey.")

    @dbus.service.method(BLUEZ_AGENT_INTERFACE, in_signature="ou", out_signature="")
    def RequestConfirmation(self, device: dbus.ObjectPath, passkey: int) -> None:
        """Confirm non-interactive pairing for the authorized device."""
        self._authorize_device(device)

    @dbus.service.method(BLUEZ_AGENT_INTERFACE, in_signature="o", out_signature="")
    def RequestAuthorization(self, device: dbus.ObjectPath) -> None:
        """Authorize non-interactive pairing for the selected device."""
        self._authorize_device(device)

    @dbus.service.method(BLUEZ_AGENT_INTERFACE, in_signature="os", out_signature="")
    def AuthorizeService(self, device: dbus.ObjectPath, uuid: str) -> None:
        """Authorize a Bluetooth service for the selected device."""
        self._authorize_device(device)

    @dbus.service.method(BLUEZ_AGENT_INTERFACE, in_signature="", out_signature="")
    def Cancel(self) -> None:
        """Handle cancellation of an outstanding agent request."""
        logger.debug("BlueZ canceled the Bluetooth pairing agent request.")
