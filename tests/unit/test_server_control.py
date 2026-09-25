from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.server_control import (
    ServerController,
    ServerState,
    get_lan_ip,
    get_lan_url,
    verify_application_on_port,
)


def test_lan_ip_and_url_detection() -> None:
    ip = get_lan_ip()
    assert ip
    url = get_lan_url(8000)
    assert url.startswith("http://")
    assert ":8000" in url


def test_server_controller_status_when_stopped() -> None:
    controller = ServerController(host="0.0.0.0", port=59999)
    with patch("app.server_control.is_port_open", return_value=False):
        status = controller.get_status()
        assert isinstance(status, ServerState)
        assert status.status == "Stopped"
        assert status.port == 59999
        assert status.isOurApp is False
        assert status.to_dict()["status"] == "Stopped"


def test_server_controller_status_when_running() -> None:
    controller = ServerController(host="0.0.0.0", port=8000)
    with (
        patch("app.server_control.is_port_open", return_value=True),
        patch("app.server_control.verify_application_on_port", return_value=True),
        patch("app.server_control.find_port_pids", return_value=[12345]),
    ):
        status = controller.get_status()
        assert status.status == "Running"
        assert status.pids == [12345]
        assert status.isOurApp is True
        assert status.port == 8000


def test_server_controller_status_when_occupied_by_foreign_process() -> None:
    controller = ServerController(host="0.0.0.0", port=8000)
    with (
        patch("app.server_control.is_port_open", return_value=True),
        patch("app.server_control.verify_application_on_port", return_value=False),
        patch("app.server_control.find_port_pids", return_value=[99999]),
    ):
        status = controller.get_status()
        assert status.status == "Error"
        assert status.isOurApp is False
        assert "unrecognized process" in status.message


def test_start_server_avoids_duplicate_process() -> None:
    controller = ServerController(host="0.0.0.0", port=8000)
    with (
        patch("app.server_control.is_port_open", return_value=True),
        patch("app.server_control.verify_application_on_port", return_value=True),
        patch("app.server_control.find_port_pids", return_value=[12345]),
        patch("subprocess.Popen") as mock_popen,
    ):
        state = controller.start()
        assert state.status == "Running"
        assert "already running" in state.message
        # Crucial: duplicate process must not be spawned!
        mock_popen.assert_not_called()


def test_start_server_launches_uvicorn_when_stopped() -> None:
    controller = ServerController(host="0.0.0.0", port=8000)
    # 1st call get_status returns Stopped, then after start returns Running
    with (
        patch.object(
            controller,
            "get_status",
            side_effect=[
                ServerState(
                    "Stopped", 8000, "0.0.0.0", [], "192.168.1.152",
                    "http://192.168.1.152:8000", False, "stopped", "/venv",
                ),
                ServerState(
                    "Running", 8000, "0.0.0.0", [54321], "192.168.1.152",
                    "http://192.168.1.152:8000", True, "running", "/venv",
                ),
            ],
        ),
        patch("subprocess.Popen") as mock_popen,
        patch("app.server_control.is_port_open", return_value=True),
        patch("app.server_control.verify_application_on_port", return_value=True),
    ):
        state = controller.start()
        assert state.status == "Running"
        mock_popen.assert_called_once()
        args = mock_popen.call_args[0][0]
        assert "app.main:app" in args
        assert "--host" in args and "0.0.0.0" in args
        assert "--port" in args and "8000" in args


def test_stop_server_terminates_pids() -> None:
    controller = ServerController(host="0.0.0.0", port=8000)
    port_8000_open = [True, False]

    def mock_port_open(port: int, *args: object, **kwargs: object) -> bool:
        if port == 8000:
            return port_8000_open.pop(0) if port_8000_open else False
        return True

    with (
        patch("app.server_control.find_port_pids", side_effect=[[12345], [], []]),
        patch("app.server_control.is_port_open", side_effect=mock_port_open),
        patch("app.server_control.ensure_manager_running"),
        patch("os.kill") as mock_kill,
    ):
        state = controller.stop()
        mock_kill.assert_called()
        assert state.status == "Stopped"


def test_verify_application_on_port_true() -> None:
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b'{"success":true,"data":{"status":"ok"}}'
    mock_resp.__enter__.return_value = mock_resp
    with patch("urllib.request.urlopen", return_value=mock_resp):
        assert verify_application_on_port(8000) is True


def test_verify_application_on_port_false_on_connection_error() -> None:
    with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
        assert verify_application_on_port(8000) is False
