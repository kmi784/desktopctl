import logging

logger = logging.getLogger(__name__)

# public API ---------------------------------------------------------------------------


class BluetoothError(RuntimeError):
    """Indicate that a Bluetooth operation failed."""
