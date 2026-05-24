from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None  # type: ignore[assignment]


@dataclass(frozen=True)
class Settings:
    database_url: str = "sqlite:///./data/app.db"
    object_storage_dir: Path = Path("./data/objects")
    deepseek_api_key: str | None = None
    deepseek_api_key_file: Path | None = None
    deepseek_model: str = "deepseek-v4-flash"
    github_token: str | None = None
    github_provider: str = "real_trending_only"
    model_provider: str = "minimax"
    tts_provider: str = "minimax"
    minimax_api_key: str | None = None
    minimax_api_key_file: Path | None = Path("doc/minimax token.txt")
    minimax_cli_path: str = "mmx"
    minimax_cli_region: str = "cn"
    minimax_text_model: str = "MiniMax-M2.7"
    minimax_tts_model: str = "speech-2.8-hd"
    minimax_tts_endpoint: str = "https://api.minimax.io/v1/t2a_v2"
    minimax_tts_voice_id: str | None = "Chinese (Mandarin)_Sweet_Lady"
    minimax_runtime_tmp_dir: Path = Path("data/runtime_tmp")
    render_provider: str = "ffmpeg_info"
    app_env: str = "local"


def load_settings() -> Settings:
    if load_dotenv is not None:
        load_dotenv()
    key_file = os.getenv("DEEPSEEK_API_KEY_FILE")
    key = os.getenv("DEEPSEEK_API_KEY") or None
    if key is None:
        configured_key_file = Path(key_file) if key_file else Path("doc/deepseek api.txt")
        if configured_key_file.exists():
            key = configured_key_file.read_text(encoding="utf-8").strip() or None
    minimax_key_file = os.getenv("MINIMAX_API_KEY_FILE")
    minimax_key = os.getenv("MINIMAX_API_KEY") or None
    configured_minimax_key_file = (
        Path(minimax_key_file) if minimax_key_file else Path("doc/minimax token.txt")
    )
    if minimax_key is None and configured_minimax_key_file.exists():
        minimax_key = configured_minimax_key_file.read_text(encoding="utf-8").strip() or None
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./data/app.db"),
        object_storage_dir=Path(os.getenv("OBJECT_STORAGE_DIR", "./data/objects")),
        deepseek_api_key=key,
        deepseek_api_key_file=Path(key_file) if key_file else None,
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        github_token=os.getenv("GITHUB_TOKEN") or None,
        github_provider=os.getenv("GITHUB_PROVIDER", "real_trending_only"),
        model_provider=os.getenv("MODEL_PROVIDER", "minimax"),
        tts_provider=os.getenv("TTS_PROVIDER", "minimax"),
        minimax_api_key=minimax_key,
        minimax_api_key_file=configured_minimax_key_file,
        minimax_cli_path=os.getenv("MINIMAX_CLI_PATH", "mmx"),
        minimax_cli_region=os.getenv("MINIMAX_CLI_REGION", "cn"),
        minimax_text_model=os.getenv("MINIMAX_TEXT_MODEL", "MiniMax-M2.7"),
        minimax_tts_model=os.getenv("MINIMAX_TTS_MODEL", "speech-2.8-hd"),
        minimax_tts_endpoint=os.getenv(
            "MINIMAX_TTS_ENDPOINT", "https://api.minimax.io/v1/t2a_v2"
        ),
        minimax_tts_voice_id=os.getenv(
            "MINIMAX_TTS_VOICE_ID", "Chinese (Mandarin)_Sweet_Lady"
        )
        or None,
        minimax_runtime_tmp_dir=Path(os.getenv("MINIMAX_RUNTIME_TMP_DIR", "data/runtime_tmp")),
        render_provider=os.getenv("RENDER_PROVIDER", "ffmpeg_info"),
        app_env=os.getenv("APP_ENV", "local"),
    )
