from subprocess import CalledProcessError, CompletedProcess

import pytest

from desktopctl.wifi import nmcli_api


@pytest.mark.parametrize(
    ("nmcli_output", "expected"),
    [("enabled", True), ("disabled", False)],
    ids=["enabled", "disabled"],
)
def test_wifi_is_enabled(monkeypatch: pytest.MonkeyPatch, nmcli_output, expected):
    def fake_run_nmcli(*args, input_text=None):
        assert args == ("radio", "wifi")
        assert input_text is None
        return nmcli_output

    monkeypatch.setattr(nmcli_api, "_run_nmcli", fake_run_nmcli)

    assert nmcli_api.wifi_is_enabled() is expected


def test_list_visible_wifi_networks(monkeypatch: pytest.MonkeyPatch):
    def fake_run_nmcli(*args, input_text=None):
        assert args == (
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

        assert input_text is None

        return "12:WPA1::Dummy:WiFi\n23:WPA2:*:Dummy\n34:WPA3:+:WiFi\n"

    monkeypatch.setattr(nmcli_api, "_run_nmcli", fake_run_nmcli)

    result = nmcli_api.list_visible_wifi_networks()

    assert len(result) == 3
    assert all(isinstance(obj, nmcli_api.WifiNetwork) for obj in result)

    wifi1: nmcli_api.WifiNetwork = result[0]
    assert wifi1.ssid == "Dummy:WiFi"
    assert wifi1.signal == 12
    assert wifi1.security == "WPA1"
    assert not wifi1.connected

    wifi2: nmcli_api.WifiNetwork = result[1]
    assert wifi2.ssid == "Dummy"
    assert wifi2.signal == 23
    assert wifi2.security == "WPA2"
    assert wifi2.connected

    wifi3: nmcli_api.WifiNetwork = result[2]
    assert wifi3.ssid == "WiFi"
    assert wifi3.signal == 34
    assert wifi3.security == "WPA3"
    assert not wifi3.connected


@pytest.mark.parametrize(
    ("wifi1", "wifi2", "expected"),
    [
        (
            "12:WPA2::Dummy\n",
            "23:WPA2::Dummy\n",
            nmcli_api.WifiNetwork("Dummy", 23, "WPA2", False),
        ),
        (
            "12:WPA2:*:Dummy\n",
            "23:WPA2::Dummy\n",
            nmcli_api.WifiNetwork("Dummy", 12, "WPA2", True),
        ),
        (
            "23:WPA2::Dummy\n",
            "12:WPA2:*:Dummy\n",
            nmcli_api.WifiNetwork("Dummy", 12, "WPA2", True),
        ),
    ],
    ids=[
        "prefer-greater-signal-strength",
        "prefer-connected-wifi-before",
        "prefer-connected-wifi-after",
    ],
)
def test_list_visible_wifi_networks_duplicated_ssid(
    monkeypatch: pytest.MonkeyPatch, wifi1, wifi2, expected
):
    def fake_run_nmcli(*args, input_text=None):
        assert args == (
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

        assert input_text is None

        return wifi1 + wifi2

    monkeypatch.setattr(nmcli_api, "_run_nmcli", fake_run_nmcli)

    result = nmcli_api.list_visible_wifi_networks()

    assert len(result) == 1
    assert isinstance(result[0], nmcli_api.WifiNetwork)
    assert result[0] == expected


def test_show_connected_wifi(monkeypatch: pytest.MonkeyPatch):
    connected_network = nmcli_api.WifiNetwork("WiFi", 67, "WPA2", True)
    networks = [
        nmcli_api.WifiNetwork("Dummy WiFi", 34, "WPA2", False),
        connected_network,
    ]
    monkeypatch.setattr(nmcli_api, "list_visible_wifi_networks", lambda: networks)

    assert nmcli_api.show_connected_wifi() == connected_network


def test_show_connected_wifi_returns_none(monkeypatch: pytest.MonkeyPatch):
    networks = [nmcli_api.WifiNetwork("Dummy WiFi", 34, "WPA2", False)]
    monkeypatch.setattr(nmcli_api, "list_visible_wifi_networks", lambda: networks)

    assert nmcli_api.show_connected_wifi() is None


def test_list_saved_wifi_networks(monkeypatch: pytest.MonkeyPatch):

    dummy_uuid = "123abc"

    def fake_run_nmcli(*args, input_text=None):
        assert input_text is None

        if "uuid" in args:
            assert args == (
                "--escape",
                "no",
                "--get-values",
                "802-11-wireless.ssid",
                "connection",
                "show",
                "uuid",
                dummy_uuid,
            )

            return "Dummy"

        assert args == (
            "--terse",
            "--escape",
            "no",
            "--fields",
            "UUID,TYPE,NAME",
            "connection",
            "show",
        )

        return f"{dummy_uuid}:802-11-wireless:Dummy:WiFi\n345def:802-3-ethernet:Dummy\n"

    monkeypatch.setattr(nmcli_api, "_run_nmcli", fake_run_nmcli)

    result = nmcli_api.list_saved_wifi_networks()

    assert len(result) == 1
    assert all(isinstance(obj, nmcli_api.SavedWifiProfile) for obj in result)

    wifi: nmcli_api.SavedWifiProfile = result[0]
    assert wifi.uuid == "123abc"
    assert wifi.profile_name == "Dummy:WiFi"
    assert wifi.ssid == "Dummy"


@pytest.mark.parametrize(
    ("state", "enable"),
    [("on", True), ("off", False)],
    ids=["enable", "disable"],
)
def test_enable_wifi(monkeypatch: pytest.MonkeyPatch, state, enable):
    def fake_run_nmcli(*args, input_text=None):
        assert args == ("radio", "wifi", state)
        assert input_text is None

    monkeypatch.setattr(nmcli_api, "_run_nmcli", fake_run_nmcli)
    nmcli_api.enable_wifi(enable)


def test_scan_wifi_networks(monkeypatch: pytest.MonkeyPatch):
    def fake_run_nmcli(*args, input_text=None):
        assert args == ("device", "wifi", "rescan")
        assert input_text is None

    monkeypatch.setattr(nmcli_api, "_run_nmcli", fake_run_nmcli)
    nmcli_api.scan_wifi_networks()


@pytest.mark.parametrize(
    ("password", "expected_args", "expected_input"),
    [
        (None, ("device", "wifi", "connect", "WiFi"), None),
        ("1234!", ("--ask", "device", "wifi", "connect", "WiFi"), "1234!\n"),
    ],
    ids=["without-password", "with-password"],
)
def test_connect_wifi_networks(
    monkeypatch: pytest.MonkeyPatch, password, expected_args, expected_input
):

    def fake_run_nmcli(*args, input_text=None):
        assert args == expected_args
        assert input_text == expected_input

    monkeypatch.setattr(nmcli_api, "_run_nmcli", fake_run_nmcli)
    nmcli_api.connect_wifi_network("WiFi", password)


def test_disconnect_wifi_networks_raises_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(nmcli_api, "_get_connected_wifi_device", lambda: None)
    with pytest.raises(nmcli_api.WifiError, match="active WiFi connection"):
        nmcli_api.disconnect_wifi_network()


def test_disconnect_wifi_networks(monkeypatch: pytest.MonkeyPatch):
    dummy_device = "Dummy"
    monkeypatch.setattr(nmcli_api, "_get_connected_wifi_device", lambda: dummy_device)

    def fake_run_nmcli(*args, input_text=None):
        assert args == ("device", "disconnect", dummy_device)
        assert input_text is None

    monkeypatch.setattr(nmcli_api, "_run_nmcli", fake_run_nmcli)
    nmcli_api.disconnect_wifi_network()


def test_forget_wifi(monkeypatch: pytest.MonkeyPatch):
    dummy_uuid = "123abc"

    def fake_run_nmcli(*args, input_text=None):
        assert args == ("connection", "delete", "uuid", dummy_uuid)
        assert input_text is None

    monkeypatch.setattr(nmcli_api, "_run_nmcli", fake_run_nmcli)
    nmcli_api.forget_wifi(dummy_uuid)


def test_run_nmcli(monkeypatch: pytest.MonkeyPatch):
    def fake_run(*args, **kwargs):
        assert args == (["nmcli", "radio", "wifi"],)
        assert kwargs == {
            "check": True,
            "capture_output": True,
            "text": True,
            "input": "dummy input\n",
        }

        return CompletedProcess(
            args=args[0],
            returncode=0,
            stdout=" enabled\n",
            stderr="",
        )

    monkeypatch.setattr(nmcli_api, "run", fake_run)

    result = nmcli_api._run_nmcli(
        "radio",
        "wifi",
        input_text="dummy input\n",
    )

    assert result == "enabled"


def test_run_nmcli_raises_error_when_command_is_missing(
    monkeypatch: pytest.MonkeyPatch,
):
    def fake_run(*args, **kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(nmcli_api, "run", fake_run)

    with pytest.raises(nmcli_api.WifiError, match="nmcli is not installed"):
        nmcli_api._run_nmcli("radio", "wifi")


@pytest.mark.parametrize(
    ("stderr", "expected_message"),
    [
        ("NetworkManager failed.\n", "NetworkManager failed."),
        ("", "nmcli command failed."),
    ],
    ids=["stderr", "fallback-message"],
)
def test_run_nmcli_raises_error_when_command_fails(
    monkeypatch: pytest.MonkeyPatch,
    stderr,
    expected_message,
):
    def fake_run(*args, **kwargs):
        raise CalledProcessError(
            returncode=1,
            cmd=args[0],
            stderr=stderr,
        )

    monkeypatch.setattr(nmcli_api, "run", fake_run)

    with pytest.raises(nmcli_api.WifiError) as error:
        nmcli_api._run_nmcli("radio", "wifi")

    assert str(error.value) == expected_message


@pytest.mark.parametrize(
    ("nmcli_output", "expected_device"),
    [
        (
            "lo:loopback:connected (externally)\n"
            "wlp0s20f3:wifi:connected\n"
            "enp0s31f6:ethernet:unavailable\n",
            "wlp0s20f3",
        ),
        (
            "p2p-dev-wlp0s20f3:wifi-p2p:disconnected\nenp0s31f6:ethernet:connected\n",
            None,
        ),
    ],
    ids=["connected", "not-connected"],
)
def test_get_connected_wifi_device(
    monkeypatch: pytest.MonkeyPatch,
    nmcli_output,
    expected_device,
):
    def fake_run_nmcli(*args, input_text=None):
        assert args == (
            "--terse",
            "--escape",
            "no",
            "--fields",
            "DEVICE,TYPE,STATE",
            "device",
            "status",
        )
        assert input_text is None
        return nmcli_output

    monkeypatch.setattr(nmcli_api, "_run_nmcli", fake_run_nmcli)

    assert nmcli_api._get_connected_wifi_device() == expected_device
