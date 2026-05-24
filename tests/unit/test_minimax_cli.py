from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

from app.config import Settings
from app.content_generation import MiniMaxCliModelAdapter
from app.contracts.errors import AppError
from app.main import create_services
from app.minimax_cli import MiniMaxCliRunner
from app.tts_subtitle import MiniMaxCliTTSAdapter


def test_minimax_cli_runner_uses_non_interactive_json_command_without_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def fake_run(*popenargs: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        command = cast(list[str], popenargs[0])
        captured["command"] = command
        captured["cwd"] = kwargs["cwd"]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"content": "ok"}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = MiniMaxCliRunner("mmx", "cn", tmp_path / "runtime")

    assert runner.run_json(["text", "chat", "--model", "MiniMax-M2.7", "--message", "hello"])

    command = cast(list[str], captured["command"])
    assert command[1:7] == [
        "--no-color",
        "--non-interactive",
        "--output",
        "json",
        "--region",
        "cn",
    ]
    assert "mmx" in command[0].lower()
    assert "text" in command
    assert "chat" in command
    assert "secret" not in " ".join(command).lower()
    assert captured["cwd"] == tmp_path / "runtime"


def test_minimax_cli_model_adapter_extracts_assistant_content(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(*popenargs: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        command = cast(list[str], popenargs[0])
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps({"choices": [{"message": {"content": '{"title":"ok"}'}}]}),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = MiniMaxCliModelAdapter(MiniMaxCliRunner(runtime_tmp_dir=tmp_path / "runtime"))

    assert adapter.generate("prompt") == '{"title":"ok"}'


def test_minimax_cli_tts_writes_text_file_and_reads_mp3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, Any] = {}

    def fake_run(*popenargs: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        command = cast(list[str], popenargs[0])
        if command[0] == "ffprobe":
            return subprocess.CompletedProcess(command, 0, stdout="1.5\n", stderr="")
        captured["command"] = command
        out_path = Path(command[command.index("--out") + 1])
        text_path = Path(command[command.index("--text-file") + 1])
        captured["text"] = text_path.read_text(encoding="utf-8")
        out_path.write_bytes(b"mock mp3")
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    adapter = MiniMaxCliTTSAdapter(
        MiniMaxCliRunner(runtime_tmp_dir=tmp_path / "runtime"),
        voice_id="Chinese (Mandarin)_News_Anchor",
    )

    result = adapter.synthesize("hello", "default_cn_tech")

    command = cast(list[str], captured["command"])
    assert result["audioBytes"] == b"mock mp3"
    assert result["contentType"] == "audio/mpeg"
    assert result["durationMs"] == 1500
    assert result["voice"] == "Chinese (Mandarin)_News_Anchor"
    assert captured["text"] == "hello"
    assert "--text-file" in command
    assert "--out" in command
    assert command[command.index("--speed") + 1] == "1.2"
    assert "MINIMAX_API_KEY" not in " ".join(command)


@pytest.mark.parametrize(
    ("stderr", "expected_code"),
    [
        ("please run mmx auth login first", "MINIMAX_CLI_AUTH_FAILED"),
        ("insufficient balance for token plan route", "MINIMAX_TOKEN_PLAN_BALANCE_ROUTE_FAILED"),
        ("voice does not exist", "MINIMAX_VOICE_UNAVAILABLE"),
    ],
)
def test_minimax_cli_runner_maps_failures_to_app_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stderr: str,
    expected_code: str,
) -> None:
    def fake_run(*popenargs: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        command = cast(list[str], popenargs[0])
        return subprocess.CompletedProcess(command, 1, stdout="", stderr=stderr)

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = MiniMaxCliRunner(runtime_tmp_dir=tmp_path / "runtime")

    with pytest.raises(AppError) as exc:
        runner.run(["text", "chat", "--model", "MiniMax-M2.7", "--message", "hello"])

    assert exc.value.code == expected_code
    serialized = json.dumps(exc.value.to_dict())
    assert "Authorization" not in serialized
    assert "secret-token" not in serialized


def test_minimax_cli_not_found_maps_to_install_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fake_run(*popenargs: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", fake_run)
    runner = MiniMaxCliRunner("missing-mmx", runtime_tmp_dir=tmp_path / "runtime")

    with pytest.raises(AppError) as exc:
        runner.run(["quota", "show"])

    assert exc.value.code == "MINIMAX_CLI_NOT_FOUND"


def test_create_services_selects_minimax_cli_adapters(settings: Settings) -> None:
    configured = Settings(
        database_url=settings.database_url,
        object_storage_dir=settings.object_storage_dir,
        model_provider="minimax",
        tts_provider="minimax",
        minimax_runtime_tmp_dir=settings.object_storage_dir / "runtime",
    )

    services = create_services(configured)

    assert isinstance(services.content.model_adapter, MiniMaxCliModelAdapter)
    assert isinstance(services.tts.adapter, MiniMaxCliTTSAdapter)
