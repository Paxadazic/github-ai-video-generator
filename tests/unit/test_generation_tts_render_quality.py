from __future__ import annotations

import io
import json
import urllib.request
import wave
from pathlib import Path
from typing import Any, cast

import pytest

from app.config import Settings, load_settings
from app.content_generation import ContentGenerationService, MockModelAdapter
from app.contracts.errors import AppError
from app.contracts.statuses import TaskStatus
from app.main import Services, create_services
from app.tts_subtitle import (
    MiniMaxCliTTSAdapter,
    MiniMaxTTSAdapter,
    MockTTSAdapter,
    TTSSubtitleService,
)
from tests.helpers import candidate, script_payload


class VariableDurationWavAdapter:
    def __init__(self, durations_ms: list[int]) -> None:
        self.durations_ms = durations_ms
        self.calls = 0

    def synthesize(self, text: str, voice: str, config: Any = None) -> dict[str, object]:
        duration_ms = self.durations_ms[self.calls]
        self.calls += 1
        sample_rate = 8_000
        frames = int(sample_rate * duration_ms / 1000)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b"\x00\x00" * frames)
        return {
            "audioBytes": buffer.getvalue(),
            "contentType": "audio/wav",
            "durationMs": duration_ms,
            "voice": voice,
        }


class AlwaysBrokenModelAdapter:
    def generate(self, prompt: str, config: Any = None) -> str:
        return "not-json"

    def repair(self, invalid_output: str, error: str, config: Any = None) -> str:
        return "still-not-json"


def test_content_generation_valid_and_repair_paths(services: Services) -> None:
    services.repository.upsert_candidates([candidate("owner/project")])
    task = services.repository.create_task("owner/project")
    result = services.content.generate_script("owner/project", task_id=task["taskId"])
    assert result["script"]["title"]
    assert result["scriptUrl"].startswith("file:")

    adapter = MockModelAdapter(outputs=["not-json", json.dumps(script_payload())])
    service = ContentGenerationService(services.repository, services.object_store, adapter)
    repaired = service.generate_script("owner/project", task_id=task["taskId"])
    repaired_script = cast(dict[str, Any], repaired["script"])
    repaired_segments = cast(list[dict[str, Any]], repaired_script["segments"])
    assert repaired_segments[0]["voiceText"]


def test_content_generation_uses_metadata_fallback_after_model_failures(
    services: Services,
) -> None:
    services.repository.upsert_candidates([candidate("owner/project")])
    task = services.repository.create_task("owner/project")
    service = ContentGenerationService(
        services.repository,
        services.object_store,
        AlwaysBrokenModelAdapter(),
    )

    result = service.generate_script("owner/project", task_id=task["taskId"])

    assert result["fallbackUsed"] is True
    attempt_errors = cast(list[dict[str, Any]], result["attemptErrors"])
    script_url = cast(str, result["scriptUrl"])
    assert len(attempt_errors) == 3
    assert script_url.startswith("file:")
    script = cast(dict[str, Any], result["script"])
    assert script["title"] == "GitHub 今日项目：project"
    assert services.repository.list_assets(task["taskId"])[0]["type"] == "script"


def test_content_generation_blocks_unsupported_facts(services: Services) -> None:
    services.repository.upsert_candidates([candidate("owner/project")])
    bad = script_payload()
    bad["description"] = "verified performance and safe"
    adapter = MockModelAdapter(outputs=[json.dumps(bad), json.dumps(bad), json.dumps(bad)])
    service = ContentGenerationService(services.repository, services.object_store, adapter)
    with pytest.raises(AppError):
        service.generate_script("owner/project")


def test_tts_subtitle_render_and_quality_happy_path(services: Services) -> None:
    services.repository.upsert_candidates([candidate("owner/project")])
    task = services.repository.create_task("owner/project")
    script_written = services.object_store.write_json("scripts", script_payload())
    script_asset = services.repository.add_asset(
        task["taskId"],
        "script",
        script_written["url"],
        "application/json",
        script_written["sizeBytes"],
        script_written["checksum"],
        {"title": "Project is trending"},
    )

    tts = services.tts.generate_tts(task["taskId"], script_payload())
    subtitle_doc = cast(dict[str, Any], tts["subtitle"])
    assert subtitle_doc["level"] == "sentence"
    items = cast(list[dict[str, Any]], subtitle_doc["items"])
    assert all(items[index]["startMs"] < items[index]["endMs"] for index in range(len(items)))

    render = services.renderer.render_video(
        task["taskId"],
        "github_daily_code_ppt_v1",
        script_asset["url"],
        tts["audioUrl"],
        tts["subtitleUrl"],
    )
    result = cast(dict[str, Any], render["result"])
    metadata = cast(dict[str, Any], result["metadata"])
    assert metadata["width"] == 1080
    assert metadata["height"] == 1920
    assert metadata["videoCodec"] == "H.264"
    assert services.renderer.get_render_job(render["renderJobId"])["status"] == "rendered"

    quality = services.quality.run(
        task["taskId"],
        script_asset["url"],
        tts["audioUrl"],
        tts["subtitleUrl"],
        result["videoUrl"],
        result["coverUrl"],
    )
    assert quality["passed"] is True


def test_tts_timeline_uses_real_segment_audio_durations(services: Services) -> None:
    payload = script_payload()
    task = services.repository.create_task("owner/project")
    adapter = VariableDurationWavAdapter([1_200, 2_300, 3_400])
    service = TTSSubtitleService(services.repository, services.object_store, adapter)

    result = service.generate_tts(task["taskId"], payload)

    subtitle = cast(dict[str, Any], result["subtitle"])
    timeline = cast(list[dict[str, Any]], subtitle["slideTimeline"])
    assert [item["audioDurationMs"] for item in timeline] == [1_200, 2_300, 3_400]
    assert [item["visualDurationMs"] for item in timeline] == [1_200, 2_300, 3_400]
    assert [item["transitionDurationMs"] for item in timeline] == [300, 300, 0]
    assert subtitle["totalDurationMs"] == 7_500
    items = cast(list[dict[str, Any]], subtitle["items"])
    assert [(item["startMs"], item["endMs"]) for item in items] == [
        (0, 1_200),
        (1_500, 3_800),
        (4_100, 7_500),
    ]

    audio_asset = services.repository.get_asset(str(result["audioAssetId"]))
    assert audio_asset["metadata"]["durationSec"] == 7.5


def test_tts_audio_failure_marks_task_failed(services: Services) -> None:
    task = services.repository.create_task("owner/project")
    service = TTSSubtitleService(
        services.repository, services.object_store, MockTTSAdapter(fail=True)
    )
    with pytest.raises(AppError):
        service.generate_tts(task["taskId"], script_payload())
    assert services.repository.get_task(task["taskId"])["status"] == TaskStatus.FAILED.value


def test_minimax_tts_success_decodes_mp3_and_metadata(services: Services) -> None:
    captured: dict[str, Any] = {}

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        captured["timeout"] = timeout
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(cast(bytes, request.data).decode("utf-8"))
        return json.dumps(
            {
                "data": {"audio": b"mini mp3".hex(), "status": 2},
                "extra_info": {"audio_length": 12_345, "audio_format": "mp3"},
                "trace_id": "trace_1",
                "base_resp": {"status_code": 0, "status_msg": "success"},
            }
        ).encode("utf-8")

    adapter = MiniMaxTTSAdapter(
        "test-token",
        endpoint="https://example.test/v1/t2a_v2",
        voice_id="Chinese (Mandarin)_News_Anchor",
        transport=transport,
    )
    result = adapter.synthesize("你好，今天看一个开源项目。", "default_cn_tech")

    assert result["audioBytes"] == b"mini mp3"
    assert result["contentType"] == "audio/mpeg"
    assert result["durationMs"] == 12_345
    assert result["voice"] == "Chinese (Mandarin)_News_Anchor"
    assert captured["url"] == "https://example.test/v1/t2a_v2"
    assert captured["headers"]["Authorization"] == "Bearer test-token"
    payload = cast(dict[str, Any], captured["payload"])
    assert payload["model"] == "speech-2.8-hd"
    assert payload["output_format"] == "hex"
    assert payload["audio_setting"]["format"] == "mp3"
    assert payload["voice_setting"]["voice_id"] == "Chinese (Mandarin)_News_Anchor"

    task = services.repository.create_task("owner/project")
    service = TTSSubtitleService(services.repository, services.object_store, adapter)
    tts = service.generate_tts(task["taskId"], script_payload(), "default_cn_tech")
    audio_asset = services.repository.get_asset(str(tts["audioAssetId"]))
    assert audio_asset["contentType"] == "audio/mpeg"
    assert audio_asset["metadata"]["voice"] == "Chinese (Mandarin)_News_Anchor"


def test_minimax_tts_error_is_unified_and_does_not_leak_token() -> None:
    token = "secret-minimax-token"

    def transport(request: urllib.request.Request, timeout: float) -> bytes:
        return json.dumps(
            {
                "data": None,
                "trace_id": "trace_error",
                "base_resp": {
                    "status_code": 1001,
                    "status_msg": "voice does not exist",
                },
            }
        ).encode("utf-8")

    adapter = MiniMaxTTSAdapter(token, transport=transport)
    with pytest.raises(AppError) as exc:
        adapter.synthesize("测试语音", "default_cn_tech")

    error = exc.value.to_dict()
    assert error["code"] == "MINIMAX_TTS_FAILED"
    assert "MINIMAX_TTS_VOICE_ID" in error["message"]
    serialized_error = json.dumps(error, ensure_ascii=False)
    assert token not in serialized_error
    assert "Bearer" not in serialized_error


def test_minimax_tts_missing_key_returns_configuration_error() -> None:
    adapter = MiniMaxTTSAdapter(None)
    with pytest.raises(AppError) as exc:
        adapter.synthesize("测试语音", "default_cn_tech")
    assert exc.value.code == "MINIMAX_API_KEY_MISSING"


def test_create_services_selects_minimax_http_provider(settings: Settings) -> None:
    configured = Settings(
        database_url=settings.database_url,
        object_storage_dir=settings.object_storage_dir,
        tts_provider="minimax_http",
        minimax_api_key="test-token",
        minimax_tts_voice_id="Chinese (Mandarin)_News_Anchor",
    )
    services = create_services(configured)
    assert isinstance(services.tts.adapter, MiniMaxTTSAdapter)


def test_create_services_selects_minimax_cli_provider(settings: Settings) -> None:
    configured = Settings(
        database_url=settings.database_url,
        object_storage_dir=settings.object_storage_dir,
        tts_provider="minimax",
        minimax_runtime_tmp_dir=settings.object_storage_dir / "runtime",
    )
    services = create_services(configured)
    assert isinstance(services.tts.adapter, MiniMaxCliTTSAdapter)


def test_load_settings_reads_minimax_key_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    key_path = tmp_path / "minimax-token.txt"
    key_path.write_text("local-token\n", encoding="utf-8")
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.setenv("MINIMAX_API_KEY_FILE", str(key_path))
    settings = load_settings()
    assert settings.minimax_api_key == "local-token"
    assert settings.minimax_api_key_file == key_path


def test_render_missing_file_error(services: Services) -> None:
    task = services.repository.create_task("owner/project")
    with pytest.raises(AppError) as exc:
        services.renderer.render_video(
            task["taskId"],
            "tmpl",
            "file:///missing.json",
            "file:///missing.mp3",
            "file:///missing.json",
        )
    assert exc.value.code == "RENDER_SCRIPT_MISSING"


def test_quality_negative_paths(services: Services) -> None:
    task = services.repository.create_task("owner/project")
    broken_script = script_payload()
    broken_script["title"] = ""
    script = services.object_store.write_json("scripts", broken_script)
    audio = services.object_store.write_json("audio", {"durationSec": 60})
    subtitle = services.object_store.write_json(
        "subtitles",
        {
            "taskId": task["taskId"],
            "level": "sentence",
            "items": [{"text": "x", "startMs": 100, "endMs": 90, "segmentIndex": 0}],
        },
    )
    video = services.object_store.write_json("videos", {"metadata": {"durationSec": 70}})
    cover = services.object_store.write_bytes("covers", ".png", b"cover")
    result = services.quality.run(
        task["taskId"], script["url"], audio["url"], subtitle["url"], video["url"], cover["url"]
    )
    assert result["passed"] is False
    checks = cast(list[dict[str, Any]], result["checks"])
    failed_names = {item["name"] for item in checks if not item["passed"]}
    assert "title_not_empty" in failed_names
    assert "subtitle_timestamps_increasing" in failed_names
    assert "audio_video_duration_delta" in failed_names
