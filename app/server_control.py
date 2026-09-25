from __future__ import annotations

import contextlib
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

ServerStatus = Literal["Stopped", "Starting", "Running", "Error"]

REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python3"
VENV_UVICORN = REPO_ROOT / ".venv" / "bin" / "uvicorn"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000
DEFAULT_LAN_IP = "192.168.1.152"


def get_lan_ip() -> str:
    """Return configured or detected local LAN IPv4 address."""
    env_ip = os.environ.get("HOST_LAN_IP")
    if env_ip:
        return env_ip.strip()
    return DEFAULT_LAN_IP


def get_lan_url(port: int = DEFAULT_PORT) -> str:
    """Return full HTTP URL reachable on local network."""
    return f"http://{get_lan_ip()}:{port}"


def is_port_open(port: int = DEFAULT_PORT, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    """Check if TCP port accepts connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


def find_port_pids(port: int = DEFAULT_PORT) -> list[int]:
    """Find process IDs listening on the specified TCP port."""
    pids: list[int] = []
    # 1. Try lsof for LISTEN sockets only
    try:
        out = subprocess.check_output(
            ["lsof", "-sTCP:LISTEN", "-ti", f":{port}"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if out:
            pids = [int(p) for p in out.split() if p.isdigit()]
            if pids:
                return pids
    except Exception:
        pass

    # 2. Try ss
    try:
        out = subprocess.check_output(
            ["ss", "-tulpn"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        for line in out.splitlines():
            if f":{port}" in line and "pid=" in line:
                for part in line.split("pid=")[1:]:
                    pid_str = part.split(",")[0].split(")")[0]
                    if pid_str.isdigit():
                        pids.append(int(pid_str))
        if pids:
            return sorted(set(pids))
    except Exception:
        pass

    # 3. Try fuser
    try:
        out = subprocess.check_output(
            ["fuser", f"{port}/tcp"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        if out:
            pids = [int(p) for p in out.split() if p.isdigit()]
            if pids:
                return pids
    except Exception:
        pass

    return []


def verify_application_on_port(port: int = DEFAULT_PORT, timeout: float = 1.0) -> bool:
    """Verify that the process listening on port is this specific application."""
    url = f"http://127.0.0.1:{port}/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ServerControlHealthCheck/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = resp.read().decode("utf-8", errors="ignore")
                return '"status":"ok"' in data or '"status": "ok"' in data
    except Exception:
        pass
    return False


def ensure_manager_running(port: int = 8001) -> None:
    """Ensure the background management daemon on port 8001 is running."""
    if not is_port_open(port):
        manager_script = REPO_ROOT / "scripts" / "server_manager.py"
        if manager_script.exists():
            executable = (
                str(VENV_PYTHON)
                if VENV_PYTHON.is_file() and os.access(VENV_PYTHON, os.X_OK)
                else sys.executable
            )
            with contextlib.suppress(Exception):
                subprocess.Popen(
                    [executable, str(manager_script)],
                    cwd=str(REPO_ROOT),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )


@dataclass
class ServerState:
    status: ServerStatus
    port: int
    host: str
    pids: list[int]
    lanIp: str
    lanUrl: str
    isOurApp: bool
    message: str
    venvPath: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "port": self.port,
            "host": self.host,
            "pids": self.pids,
            "lanIp": self.lanIp,
            "lanUrl": self.lanUrl,
            "isOurApp": self.isOurApp,
            "message": self.message,
            "venvPath": self.venvPath,
        }


class ServerController:
    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        repo_root: Path | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.repo_root = repo_root or REPO_ROOT
        self.venv_uvicorn = self.repo_root / ".venv" / "bin" / "uvicorn"
        self.venv_python = self.repo_root / ".venv" / "bin" / "python3"
        self._starting_since: float | None = None

    def get_status(self) -> ServerState:
        # Guarantee manager daemon is active for out-of-band commands
        ensure_manager_running(8001)
        port_open = is_port_open(self.port)
        pids = find_port_pids(self.port)
        lan_ip = get_lan_ip()
        lan_url = get_lan_url(self.port)
        venv_path = str(self.repo_root / ".venv")

        if not port_open:
            if self._starting_since and (time.time() - self._starting_since < 10.0):
                return ServerState(
                    status="Starting",
                    port=self.port,
                    host=self.host,
                    pids=pids,
                    lanIp=lan_ip,
                    lanUrl=lan_url,
                    isOurApp=True,
                    message="Uvicorn server is starting up...",
                    venvPath=venv_path,
                )
            self._starting_since = None
            return ServerState(
                status="Stopped",
                port=self.port,
                host=self.host,
                pids=[],
                lanIp=lan_ip,
                lanUrl=lan_url,
                isOurApp=False,
                message="Server is stopped. Port 8000 is free.",
                venvPath=venv_path,
            )

        # Port is open: check if it's our application
        is_our_app = verify_application_on_port(self.port)
        if is_our_app:
            self._starting_since = None
            pid_str = f" (PID {pids[0]})" if pids else ""
            return ServerState(
                status="Running",
                port=self.port,
                host=self.host,
                pids=pids,
                lanIp=lan_ip,
                lanUrl=lan_url,
                isOurApp=True,
                message=f"FastAPI application is running on port {self.port}{pid_str}.",
                venvPath=venv_path,
            )

        # Port is open but unrecognized service
        self._starting_since = None
        pid_desc = f" (PIDs: {pids})" if pids else ""
        return ServerState(
            status="Error",
            port=self.port,
            host=self.host,
            pids=pids,
            lanIp=lan_ip,
            lanUrl=lan_url,
            isOurApp=False,
            message=f"Port {self.port} is in use by an unrecognized process{pid_desc}.",
            venvPath=venv_path,
        )

    def start(self) -> ServerState:
        """Start Uvicorn with --host 0.0.0.0 --port 8000 using existing .venv.

        Prevents duplicate processes if already running.
        """
        current = self.get_status()
        if current.status == "Running":
            pid_desc = current.pids[0] if current.pids else "unknown"
            return ServerState(
                status="Running",
                port=self.port,
                host=self.host,
                pids=current.pids,
                lanIp=current.lanIp,
                lanUrl=current.lanUrl,
                isOurApp=True,
                message=(
                    f"Server is already running on port {self.port} (PID {pid_desc}). "
                    "No duplicate started."
                ),
                venvPath=current.venvPath,
            )

        if current.status == "Error":
            return ServerState(
                status="Error",
                port=self.port,
                host=self.host,
                pids=current.pids,
                lanIp=current.lanIp,
                lanUrl=current.lanUrl,
                isOurApp=False,
                message=f"Cannot start: port {self.port} is occupied by another process.",
                venvPath=current.venvPath,
            )

        # Check venv executable
        executable: list[str]
        if self.venv_uvicorn.is_file() and os.access(self.venv_uvicorn, os.X_OK):
            executable = [str(self.venv_uvicorn)]
        elif self.venv_python.is_file() and os.access(self.venv_python, os.X_OK):
            executable = [str(self.venv_python), "-m", "uvicorn"]
        else:
            executable = [sys.executable, "-m", "uvicorn"]

        cmd = executable + ["app.main:app", "--host", self.host, "--port", str(self.port)]

        self._starting_since = time.time()
        try:
            # Spawn in detached process group
            subprocess.Popen(
                cmd,
                cwd=str(self.repo_root),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception as exc:
            self._starting_since = None
            return ServerState(
                status="Error",
                port=self.port,
                host=self.host,
                pids=[],
                lanIp=get_lan_ip(),
                lanUrl=get_lan_url(self.port),
                isOurApp=False,
                message=f"Failed to launch Uvicorn: {exc}",
                venvPath=str(self.repo_root / ".venv"),
            )

        # Wait up to 6 seconds for startup confirmation
        deadline = time.time() + 6.0
        while time.time() < deadline:
            time.sleep(0.3)
            if is_port_open(self.port) and verify_application_on_port(self.port):
                self._starting_since = None
                return self.get_status()

        # If still in progress, return Starting
        return self.get_status()

    def stop(self) -> ServerState:
        """Stop Uvicorn processes listening on port 8000."""
        self._starting_since = None
        pids = find_port_pids(self.port)
        if not pids and not is_port_open(self.port):
            return ServerState(
                status="Stopped",
                port=self.port,
                host=self.host,
                pids=[],
                lanIp=get_lan_ip(),
                lanUrl=get_lan_url(self.port),
                isOurApp=False,
                message="Server is already stopped.",
                venvPath=str(self.repo_root / ".venv"),
            )

        # Send SIGTERM to port processes
        for pid in pids:
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGTERM)

        # Wait for port to close (up to 4s)
        deadline = time.time() + 4.0
        while time.time() < deadline:
            time.sleep(0.2)
            if not is_port_open(self.port):
                break

        # If still open, force SIGKILL
        remaining = find_port_pids(self.port)
        for pid in remaining:
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGKILL)

        time.sleep(0.3)
        return self.get_status()

    def restart(self) -> ServerState:
        """Stop and cleanly restart Uvicorn on 0.0.0.0:8000."""
        self.stop()
        time.sleep(0.5)
        return self.start()
