from collections.abc import Callable
from types import ModuleType
from unittest.mock import Mock

import pytest


@pytest.fixture
def system_bus_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[ModuleType], Mock]:
    """Return a factory that installs a fake D-Bus system bus."""

    def _create(api_module: ModuleType) -> Mock:
        bus = Mock()
        bus.proxy = object()
        bus.proxies = {}
        bus.get_object_calls = []
        bus.system_bus_calls = []

        def _get_object(bus_name, object_path):
            bus.get_object_calls.append((bus_name, object_path))
            return bus.proxies.get(str(object_path), bus.proxy)

        bus.get_object.side_effect = _get_object

        def _system_bus(*args, **kwargs):
            bus.system_bus_calls.append((args, kwargs))
            return bus

        monkeypatch.setattr(api_module.dbus, "SystemBus", _system_bus)
        return bus

    return _create
