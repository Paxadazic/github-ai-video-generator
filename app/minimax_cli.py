from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

from app.contracts.errors import AppError


class MiniMaxCliRunner:
    def __init__(
        self,
        cli_path: str = "mmx",
        region: str = "cn",
        runtime_tmp_dir: Path = Path("data/runtime_tmp"),
        timeout: float = 180,
    ) -> None:
        self.cli_path = cli_path
        self.region = region
        self.runtime_tmp_dir = runtime_tmp_dir
        self.timeout = timeout

    def _resolve_cli_path(self) -> str:
        cli_path = self.cli_path
        if os.path.isabs(cli_path) or Path(cli_path).exists():
            return cli_path
        resolved = shutil.which(cli_path)
        if resolved:
            return resolved
        appdata = os.environ.get("APPDATA")
        if appdata:
            fallback = Path(appdata) / "npm" / "mmx.CMD"
            if fallback.exists():
                return str(fallback)
        return cli_path

    def run(
        self, args: Sequence[str], timeout: float | None = None
    ) -> subprocess.CompletedProcess[str]:
        self.runtime_tmp_dir.mkdir(parents=True, exist_ok=True)
        cli_path = self._resolve_cli_path()
        command = [
            cli_path,
            "--no-color",
            "--non-interactive",
            "--output",
            "json",
            "--region",
            self.region,
            *args,
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=self.runtime_tmp_dir,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                timeout=timeout or self.timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise AppError(
                "MINIMAX_CLI_NOT_FOUND",
                "MiniMax CLI was not found; install mmx-cli and configure MINIMAX_CLI_PATH",
                True,
                {
                    "cliPath": self.cli_path,
                    "resolvedPath": cli_path,
                    "pathEnv": os.environ.get("PATH", "")[:500],
                },
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise AppError(
                "MINIMAX_CLI_FAILED",
                "MiniMax CLI timed out",
                True,
                {
                    "reason": "TimeoutExpired",
                    "region": self.region,
                    "model": self._model_from_args(args),
                },
            ) from exc
        if completed.returncode != 0:
            self._raise_for_failure(completed, args)
        return completed

    def run_json(self, args: Sequence[str], timeout: float | None = None) -> object:
        completed = self.run(args, timeout)
        stdout = completed.stdout.strip()
        if not stdout:
            raise AppError(
                "MINIMAX_CLI_RESPONSE_INVALID",
                "MiniMax CLI returned an empty JSON response",
                True,
                {"region": self.region, "model": self._model_from_args(args)},
            )
        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise AppError(
                "MINIMAX_CLI_RESPONSE_INVALID",
                "MiniMax CLI returned invalid JSON",
                True,
                {
                    "region": self.region,
                    "model": self._model_from_args(args),
                    "cliOutput": _safe_cli_text(stdout),
                },
            ) from exc

    def _raise_for_failure(
        self, completed: subprocess.CompletedProcess[str], args: Sequence[str]
    ) -> None:
        combined = "\n".join(
            part.strip() for part in [completed.stderr, completed.stdout] if part.strip()
        )
        lowered = combined.lower()
        detail = {
            "returnCode": completed.returncode,
            "region": self.region,
            "model": self._model_from_args(args),
            "cliError": _safe_cli_text(combined),
        }
        if "insufficient balance" in lowered:
            raise AppError(
                "MINIMAX_TOKEN_PLAN_BALANCE_ROUTE_FAILED",
                (
                    "MiniMax Token Plan quota route failed with insufficient balance; "
                    "include the model, region, and CLI error when contacting MiniMax"
                ),
                True,
                detail,
            )
        if _looks_like_auth_failure(lowered):
            raise AppError(
                "MINIMAX_CLI_AUTH_FAILED",
                "MiniMax CLI authentication failed; run `mmx auth login` and verify the account",
                True,
                detail,
            )
        if _looks_like_voice_failure(lowered):
            raise AppError(
                "MINIMAX_VOICE_UNAVAILABLE",
                "MiniMax voice is unavailable; configure MINIMAX_TTS_VOICE_ID",
                True,
                detail,
            )
        raise AppError("MINIMAX_CLI_FAILED", "MiniMax CLI command failed", True, detail)

    def _model_from_args(self, args: Sequence[str]) -> str | None:
        try:
            model_index = args.index("--model")
        except ValueError:
            return None
        if model_index + 1 >= len(args):
            return None
        return args[model_index + 1]


def _looks_like_auth_failure(lowered_text: str) -> bool:
    auth_markers = [
        "not logged",
        "not login",
        "login required",
        "auth login",
        "auth failed",
        "authentication failed",
        "unauthorized",
        "invalid api key",
        "api key invalid",
        "401",
    ]
    return any(marker in lowered_text for marker in auth_markers)


def _looks_like_voice_failure(lowered_text: str) -> bool:
    if "voice" not in lowered_text:
        return False
    voice_markers = ["not exist", "does not exist", "not found", "unavailable", "invalid"]
    return any(marker in lowered_text for marker in voice_markers)


def _safe_cli_text(text: str, limit: int = 1200) -> str:
    sanitized = re.sub(r"(?i)bearer\s+[a-z0-9._\-]+", "Bearer [REDACTED]", text)
    sanitized = re.sub(
        r"(?i)(api[_-]?key|token|authorization)(\s*[:=]\s*)(\S+)",
        r"\1\2[REDACTED]",
        sanitized,
    )
    sanitized = "\n".join(
        line
        for line in sanitized.splitlines()
        if not re.search(r"(?i)(full config|config file|credential)", line)
    )
    return sanitized[:limit]
