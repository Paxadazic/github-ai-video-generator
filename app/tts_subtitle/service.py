from __future__ import annotations

import io
import json
import logging
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import wave
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, Protocol, cast

from app.contracts.errors import AppError
from app.contracts.schemas import SubtitleDocument, SubtitleItem, TTSConfig, VideoScript
from app.minimax_cli import MiniMaxCliRunner
from app.storage.object_store import LocalObjectStore
from app.storage.repository import SQLiteRepository

logger = logging.getLogger(__name__)
SLIDE_TRANSITION_MS = 300


class TTSAdapter(Protocol):
    def synthesize(
        self, text: str, voice: str, config: TTSConfig | None = None
    ) -> dict[str, object]: ...


class MockTTSAdapter:
    def __init__(
        self, fail: bool = False, timestamps: list[dict[str, object]] | None = None
    ) -> None:
        self.fail = fail
        self.timestamps = timestamps

    def synthesize(
        self, text: str, voice: str, config: TTSConfig | None = None
    ) -> dict[str, object]:
        if self.fail:
            raise AppError("TTS_AUDIO_FAILED", "Mock TTS failed", True, {})
        duration_ms = max(1_000, min(12_000, len(text.strip()) * 120))
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
            "timestamps": self.timestamps,
        }


class WindowsSapiTTSAdapter:
    def __init__(self, rate: int = 0, volume: int = 90) -> None:
        self.rate = rate
        self.volume = volume

    def synthesize(
        self, text: str, voice: str, config: TTSConfig | None = None
    ) -> dict[str, object]:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            text_path = tmp_path / "voice.txt"
            wav_path = tmp_path / "voice.wav"
            script_path = tmp_path / "speak.ps1"
            text_path.write_text(text, encoding="utf-8")
            script_path.write_text(
                "\n".join(
                    [
                        "param([string]$TextPath, [string]$WavPath)",
                        "Add-Type -AssemblyName System.Speech",
                        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer",
                        f"$s.Rate = {self.rate}",
                        f"$s.Volume = {self.volume}",
                        "$txt = Get-Content -Raw -Encoding UTF8 $TextPath",
                        "$s.SetOutputToWaveFile($WavPath)",
                        "$s.Speak($txt)",
                        "$s.Dispose()",
                    ]
                ),
                encoding="utf-8",
            )
            try:
                subprocess.run(
                    [
                        "powershell",
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(script_path),
                        str(text_path),
                        str(wav_path),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=120,
                )
            except (
                FileNotFoundError,
                subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
            ) as exc:
                raise AppError(
                    "WINDOWS_TTS_FAILED",
                    "Windows SAPI TTS failed",
                    True,
                    {"reason": exc.__class__.__name__, "voice": voice},
                ) from exc
            if not wav_path.exists():
                raise AppError(
                    "WINDOWS_TTS_FAILED",
                    "Windows SAPI TTS did not create a WAV file",
                    True,
                    {"voice": voice},
                )
            duration_ms = _wav_duration_ms(wav_path)
            return {
                "audioBytes": wav_path.read_bytes(),
                "contentType": "audio/wav",
                "durationMs": duration_ms,
                "timestamps": None,
            }


class EdgeTTSAdapter:
    def __init__(
        self,
        default_voice: str = "zh-CN-XiaoxiaoNeural",
        rate: str = "+20%",
        volume: str = "+0%",
        pitch: str = "+0Hz",
    ) -> None:
        self.default_voice = default_voice
        self.rate = rate
        self.volume = volume
        self.pitch = pitch

    def synthesize(
        self, text: str, voice: str, config: TTSConfig | None = None
    ) -> dict[str, object]:
        resolved_voice = self._resolve_voice(voice)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            text_path = tmp_path / "voice.txt"
            media_path = tmp_path / "voice.mp3"
            subtitle_path = tmp_path / "voice.vtt"
            text_path.write_text(text, encoding="utf-8")
            cmd = [
                sys.executable,
                "-m",
                "edge_tts",
                "--file",
                str(text_path),
                "--voice",
                resolved_voice,
                "--rate",
                self.rate,
                "--volume",
                self.volume,
                "--pitch",
                self.pitch,
                "--write-media",
                str(media_path),
                "--write-subtitles",
                str(subtitle_path),
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=180)
            except (
                FileNotFoundError,
                subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
            ) as exc:
                raise AppError(
                    "EDGE_TTS_FAILED",
                    "Edge TTS failed",
                    True,
                    {"reason": exc.__class__.__name__, "voice": resolved_voice},
                ) from exc
            if not media_path.exists():
                raise AppError(
                    "EDGE_TTS_FAILED",
                    "Edge TTS did not create an MP3 file",
                    True,
                    {"voice": resolved_voice},
                )
            timestamps = (
                _parse_vtt_timestamps(subtitle_path.read_text(encoding="utf-8"))
                if subtitle_path.exists()
                else None
            )
            duration_ms = timestamps[-1]["endMs"] if timestamps else 0
            return {
                "audioBytes": media_path.read_bytes(),
                "contentType": "audio/mpeg",
                "durationMs": duration_ms,
                "timestamps": timestamps,
            }

    def _resolve_voice(self, voice: str) -> str:
        aliases = {
            "default_cn_tech": self.default_voice,
            "cn_male": "zh-CN-YunxiNeural",
            "cn_female": "zh-CN-XiaoxiaoNeural",
            "zh-CN-YunxiNeural": "zh-CN-YunxiNeural",
            "zh-CN-XiaoxiaoNeural": "zh-CN-XiaoxiaoNeural",
        }
        return aliases.get(voice, voice or self.default_voice)


MINIMAX_DEFAULT_CHINESE_VOICE_ID = "Chinese (Mandarin)_Sweet_Lady"


class MiniMaxTTSAdapter:
    def __init__(
        self,
        api_key: str | None,
        model: str = "speech-2.8-hd",
        endpoint: str = "https://api.minimax.io/v1/t2a_v2",
        voice_id: str | None = None,
        timeout: float = 180,
        transport: Callable[[urllib.request.Request, float], bytes] | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self.voice_id = voice_id
        self.timeout = timeout
        self.transport = transport or self._default_transport

    def synthesize(
        self, text: str, voice: str, config: TTSConfig | None = None
    ) -> dict[str, object]:
        if not self.api_key:
            raise AppError("MINIMAX_API_KEY_MISSING", "MiniMax API key is not configured", True, {})
        effective = config or TTSConfig(voiceId=voice)
        resolved_voice = self._resolve_voice(effective.voiceId or voice)
        payload = {
            "model": effective.model or self.model,
            "text": text,
            "stream": False,
            "language_boost": effective.language,
            "output_format": "hex",
            "voice_setting": {
                "voice_id": resolved_voice,
                "speed": effective.speed,
                "vol": effective.volume,
                "pitch": effective.pitch,
            },
            "audio_setting": {
                "sample_rate": effective.sampleRate,
                "bitrate": effective.bitrate,
                "format": effective.format,
                "channel": effective.channels,
            },
        }
        request = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        raw = self._send(request)
        self._ensure_success(raw, resolved_voice)
        audio_hex = self._extract_audio_hex(raw)
        try:
            audio_bytes = bytes.fromhex(audio_hex)
        except ValueError as exc:
            raise AppError(
                "MINIMAX_RESPONSE_INVALID",
                "MiniMax returned invalid hex audio",
                True,
                self._safe_response_detail(raw),
            ) from exc
        return {
            "audioBytes": audio_bytes,
            "contentType": _content_type_for_audio_format(effective.format),
            "durationMs": self._duration_ms(raw),
            "timestamps": None,
            "voice": resolved_voice,
        }

    def _send(self, request: urllib.request.Request) -> dict[str, Any]:
        try:
            response_body = self.transport(request, self.timeout)
            raw = json.loads(response_body.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = {"httpStatus": exc.code, "reason": exc.reason}
            parsed = _parse_json_bytes(exc.read())
            if isinstance(parsed, dict):
                detail |= self._safe_response_detail(parsed)
            raise AppError(
                "MINIMAX_TTS_FAILED", "MiniMax TTS request failed", True, detail
            ) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AppError(
                "MINIMAX_TTS_FAILED",
                "MiniMax TTS request failed",
                True,
                {"reason": exc.__class__.__name__},
            ) from exc
        if not isinstance(raw, dict):
            raise AppError("MINIMAX_RESPONSE_INVALID", "MiniMax response was invalid", True, {})
        return raw

    def _ensure_success(self, raw: dict[str, Any], voice_id: str) -> None:
        base_resp = raw.get("base_resp")
        if not isinstance(base_resp, dict):
            raise AppError(
                "MINIMAX_RESPONSE_INVALID",
                "MiniMax response did not include status",
                True,
                self._safe_response_detail(raw),
            )
        status_code = base_resp.get("status_code")
        if status_code == 0:
            return
        status_msg = str(base_resp.get("status_msg", ""))
        message = "MiniMax TTS request failed"
        status_msg_lower = status_msg.lower()
        if status_code == 2049 or "invalid api key" in status_msg_lower:
            message = "MiniMax API key is invalid; verify MINIMAX_API_KEY or MINIMAX_API_KEY_FILE"
        if "voice" in status_msg_lower and (
            "not" in status_msg_lower
            or "exist" in status_msg_lower
            or "invalid" in status_msg_lower
        ):
            message = (
                "MiniMax voice id is unavailable; configure MINIMAX_TTS_VOICE_ID "
                "with a valid Chinese voice_id"
            )
        raise AppError(
            "MINIMAX_TTS_FAILED",
            message,
            True,
            self._safe_response_detail(raw) | {"voice": voice_id},
        )

    def _extract_audio_hex(self, raw: dict[str, Any]) -> str:
        data = raw.get("data")
        if not isinstance(data, dict):
            raise AppError(
                "MINIMAX_RESPONSE_INVALID",
                "MiniMax response did not include audio data",
                True,
                self._safe_response_detail(raw),
            )
        audio = data.get("audio")
        if not isinstance(audio, str) or not audio:
            raise AppError(
                "MINIMAX_RESPONSE_INVALID",
                "MiniMax response audio was empty",
                True,
                self._safe_response_detail(raw),
            )
        return audio

    def _duration_ms(self, raw: dict[str, Any]) -> int:
        extra_info = raw.get("extra_info")
        if not isinstance(extra_info, dict):
            return 0
        return _int_value(extra_info.get("audio_length", 0))

    def _safe_response_detail(self, raw: dict[str, Any]) -> dict[str, Any]:
        detail: dict[str, Any] = {}
        trace_id = raw.get("trace_id")
        if isinstance(trace_id, str):
            detail["traceId"] = trace_id
        base_resp = raw.get("base_resp")
        if isinstance(base_resp, dict):
            detail["statusCode"] = base_resp.get("status_code")
            detail["statusMsg"] = base_resp.get("status_msg")
        return detail

    def _resolve_voice(self, voice: str) -> str:
        configured_default = self.voice_id or MINIMAX_DEFAULT_CHINESE_VOICE_ID
        aliases = {
            "default_cn_tech": configured_default,
            "cn_male": "Chinese (Mandarin)_Reliable_Executive",
            "cn_female": configured_default,
            "zh-CN-YunxiNeural": "Chinese (Mandarin)_Reliable_Executive",
            "zh-CN-XiaoxiaoNeural": configured_default,
        }
        if self.voice_id and voice in {"", "default_cn_tech", "cn_male", "cn_female"}:
            return self.voice_id
        return aliases.get(voice, voice or configured_default)

    @staticmethod
    def _default_transport(request: urllib.request.Request, timeout: float) -> bytes:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return cast(bytes, response.read())


class MiniMaxCliTTSAdapter:
    def __init__(
        self,
        runner: MiniMaxCliRunner | None = None,
        model: str = "speech-2.8-hd",
        voice_id: str | None = None,
        timeout: float = 180,
    ) -> None:
        self.runner = runner or MiniMaxCliRunner()
        self.model = model
        self.voice_id = voice_id
        self.timeout = timeout

    def synthesize(
        self, text: str, voice: str, config: TTSConfig | None = None
    ) -> dict[str, object]:
        self.runner.runtime_tmp_dir.mkdir(parents=True, exist_ok=True)
        effective = config or TTSConfig(voiceId=voice)
        resolved_voice = self._resolve_voice(effective.voiceId or voice)
        with tempfile.TemporaryDirectory(dir=self.runner.runtime_tmp_dir) as tmp:
            tmp_path = Path(tmp)
            text_path = tmp_path / "voice.txt"
            media_path = tmp_path / f"voice.{effective.format}"
            text_path.write_text(text, encoding="utf-8")
            command = [
                "speech",
                "synthesize",
                "--model",
                effective.model or self.model,
                "--text-file",
                str(text_path),
                "--voice",
                resolved_voice,
                "--language",
                effective.language,
                "--speed",
                str(effective.speed),
                "--volume",
                str(effective.volume),
                "--pitch",
                str(effective.pitch),
                "--format",
                effective.format,
                "--sample-rate",
                str(effective.sampleRate),
                "--bitrate",
                str(effective.bitrate),
                "--channels",
                str(effective.channels),
                "--out",
                str(media_path),
            ]
            if effective.subtitles:
                command.append("--subtitles")
            for item in effective.pronunciation:
                command.extend(["--pronunciation", f"{item.source}={item.target}"])
            self.runner.run(command, timeout=self.timeout)
            if not media_path.exists():
                raise AppError(
                    "MINIMAX_CLI_RESPONSE_INVALID",
                    "MiniMax CLI did not create an audio file",
                    True,
                    {"model": self.model, "region": self.runner.region, "voice": resolved_voice},
                )
            return {
                "audioBytes": media_path.read_bytes(),
                "contentType": _content_type_for_audio_format(effective.format),
                "durationMs": _ffprobe_duration_ms(media_path),
                "timestamps": None,
                "voice": resolved_voice,
            }

    def _resolve_voice(self, voice: str) -> str:
        configured_default = self.voice_id or MINIMAX_DEFAULT_CHINESE_VOICE_ID
        aliases = {
            "default_cn_tech": configured_default,
            "cn_male": "Chinese (Mandarin)_Reliable_Executive",
            "cn_female": configured_default,
            "zh-CN-YunxiNeural": "Chinese (Mandarin)_Reliable_Executive",
            "zh-CN-XiaoxiaoNeural": configured_default,
        }
        if self.voice_id and voice in {"", "default_cn_tech", "cn_male", "cn_female"}:
            return self.voice_id
        return aliases.get(voice, voice or configured_default)


class VoiceTextAssembler:
    def assemble(self, script: VideoScript) -> str:
        return "\n".join(segment.voiceText.strip() for segment in script.segments)


class TimestampNormalizer:
    def normalize(
        self, script: VideoScript, timestamps: list[dict[str, object]] | None
    ) -> SubtitleDocument:
        if timestamps:
            items = [
                SubtitleItem(
                    text=str(item["text"]),
                    startMs=_int_value(item["startMs"]),
                    endMs=_int_value(item["endMs"]),
                    segmentIndex=_int_value(item.get("segmentIndex", 0)),
                )
                for item in timestamps
            ]
            level: Literal["word", "phrase", "sentence"] = "phrase"
        else:
            items = []
            cursor = 0
            for index, segment in enumerate(script.segments):
                end = cursor + segment.durationSec * 1000
                items.append(
                    SubtitleItem(
                        text=segment.voiceText,
                        startMs=cursor,
                        endMs=end,
                        segmentIndex=index,
                    )
                )
                cursor = end
            level = "sentence"
        try:
            self._ensure_increasing(items)
        except AppError:
            if timestamps:
                return self.normalize(script, None)
            raise
        return SubtitleDocument(taskId="", level=level, items=items)

    def _ensure_increasing(self, items: list[SubtitleItem]) -> None:
        previous = -1
        for item in items:
            if item.startMs < 0 or item.startMs >= item.endMs or item.startMs < previous:
                raise AppError(
                    "SUBTITLE_TIMESTAMPS_INVALID", "Subtitle timestamps must increase", False, {}
                )
            previous = item.endMs


class SrtExporter:
    def export(self, subtitle: SubtitleDocument) -> str:
        blocks: list[str] = []
        for idx, item in enumerate(subtitle.items, start=1):
            blocks.append(
                f"{idx}\n{self._fmt(item.startMs)} --> {self._fmt(item.endMs)}\n{item.text}\n"
            )
        return "\n".join(blocks)

    def _fmt(self, ms: int) -> str:
        seconds, millis = divmod(ms, 1000)
        minutes, sec = divmod(seconds, 60)
        hours, minute = divmod(minutes, 60)
        return f"{hours:02}:{minute:02}:{sec:02},{millis:03}"


class TTSSubtitleService:
    def __init__(
        self,
        repository: SQLiteRepository,
        object_store: LocalObjectStore,
        adapter: TTSAdapter | None = None,
    ) -> None:
        self.repository = repository
        self.object_store = object_store
        self.adapter = adapter or MockTTSAdapter()
        self.assembler = VoiceTextAssembler()
        self.normalizer = TimestampNormalizer()
        self.srt_exporter = SrtExporter()

    def generate_tts(
        self,
        task_id: str,
        script_payload: dict[str, object],
        voice: str = "default_cn_tech",
        config: TTSConfig | None = None,
    ) -> dict[str, object]:
        try:
            effective_config = config or TTSConfig(voiceId=voice)
            script = VideoScript.model_validate(script_payload)
            segment_results = [
                self._synthesize_segment(
                    index, segment.voiceText.strip(), effective_config.voiceId, effective_config
                )
                for index, segment in enumerate(script.segments)
            ]
            content_type = str(segment_results[0]["contentType"])
            self._ensure_single_content_type(segment_results, content_type)
            audio_bytes = _concat_segment_audio(segment_results, content_type, SLIDE_TRANSITION_MS)
            duration_ms = sum(
                _int_value(item["durationMs"]) for item in segment_results
            ) + SLIDE_TRANSITION_MS * max(0, len(segment_results) - 1)
            audio = self.object_store.write_bytes(
                "audio", _audio_suffix_for_content_type(content_type), audio_bytes
            )
            resolved_voice = str(segment_results[0].get("voice", voice))
            slide_timeline = self._slide_timeline(segment_results)
            audio_asset = self.repository.add_asset(
                task_id,
                "audio",
                str(audio["url"]),
                content_type,
                int(audio["sizeBytes"]),
                str(audio["checksum"]),
                {
                    "durationSec": duration_ms / 1000,
                    "voice": resolved_voice,
                    "speed": effective_config.speed,
                    "ttsConfig": effective_config.model_dump(),
                    "slideTimeline": slide_timeline,
                },
            )
            subtitle = self._subtitle_from_timeline(task_id, script, slide_timeline)
            subtitle.taskId = task_id
            subtitle_payload = subtitle.model_dump()
            subtitle_payload["slideTimeline"] = slide_timeline
            subtitle_payload["totalDurationMs"] = duration_ms
            subtitle_payload["transitionMs"] = SLIDE_TRANSITION_MS
            subtitle_written = self.object_store.write_json("subtitles", subtitle_payload)
            subtitle_asset = self.repository.add_asset(
                task_id,
                "subtitle",
                str(subtitle_written["url"]),
                "application/json",
                int(subtitle_written["sizeBytes"]),
                str(subtitle_written["checksum"]),
                {
                    "level": subtitle.level,
                    "items": len(subtitle.items),
                    "slideTimeline": slide_timeline,
                },
            )
            srt = self.object_store.write_bytes(
                "subtitles", ".srt", self.srt_exporter.export(subtitle).encode("utf-8")
            )
            self.repository.add_run_log(
                "tts_subtitle",
                "generate_tts",
                True,
                task_id=task_id,
                artifact_refs={
                    "audio": audio_asset["assetId"],
                    "subtitle": subtitle_asset["assetId"],
                    "slideSync": slide_timeline,
                },
            )
            return {
                "audioUrl": audio_asset["url"],
                "subtitleUrl": subtitle_asset["url"],
                "srtUrl": srt["url"],
                "audioAssetId": audio_asset["assetId"],
                "subtitleAssetId": subtitle_asset["assetId"],
                "subtitle": subtitle_payload,
            }
        except AppError as exc:
            self.repository.fail_task(task_id, "tts_subtitle", exc)
            raise

    def _synthesize_segment(
        self, index: int, text: str, voice: str, config: TTSConfig | None = None
    ) -> dict[str, object]:
        tts = self.adapter.synthesize(text, voice, config)
        audio_bytes = cast(bytes, tts["audioBytes"])
        content_type = str(tts["contentType"])
        duration_ms = _int_value(tts.get("durationMs", 0))
        if duration_ms <= 0:
            duration_ms = _audio_bytes_duration_ms(audio_bytes, content_type)
        if duration_ms <= 0:
            duration_ms = max(1_000, len(text) * 120)
        return {
            "index": index,
            "text": text,
            "textLength": len(text),
            "audioBytes": audio_bytes,
            "contentType": content_type,
            "durationMs": duration_ms,
            "voice": tts.get("voice", voice),
        }

    def _ensure_single_content_type(
        self, segment_results: list[dict[str, object]], content_type: str
    ) -> None:
        if any(str(item["contentType"]) != content_type for item in segment_results):
            raise AppError(
                "TTS_AUDIO_MIXED_FORMATS",
                "TTS segments must use one audio format",
                True,
                {"contentTypes": [str(item["contentType"]) for item in segment_results]},
            )

    def _slide_timeline(self, segment_results: list[dict[str, object]]) -> list[dict[str, object]]:
        timeline: list[dict[str, object]] = []
        cursor = 0
        last_index = len(segment_results) - 1
        for item in segment_results:
            index = _int_value(item["index"])
            audio_duration_ms = _int_value(item["durationMs"])
            transition_ms = SLIDE_TRANSITION_MS if index < last_index else 0
            entry: dict[str, object] = {
                "slideIndex": index,
                "segmentIndex": index,
                "textLength": _int_value(item["textLength"]),
                "startMs": cursor,
                "endMs": cursor + audio_duration_ms,
                "audioDurationMs": audio_duration_ms,
                "visualDurationMs": audio_duration_ms,
                "transitionDurationMs": transition_ms,
                "totalVisualDurationMs": audio_duration_ms + transition_ms,
            }
            logger.info(
                "slide_sync index=%s text_length=%s audio_duration_ms=%s "
                "visual_duration_ms=%s transition_duration_ms=%s",
                entry["slideIndex"],
                entry["textLength"],
                entry["audioDurationMs"],
                entry["visualDurationMs"],
                entry["transitionDurationMs"],
            )
            print(
                "slide_sync "
                f"index={entry['slideIndex']} "
                f"text_length={entry['textLength']} "
                f"audio_duration_ms={entry['audioDurationMs']} "
                f"visual_duration_ms={entry['visualDurationMs']} "
                f"transition_duration_ms={entry['transitionDurationMs']}"
            )
            timeline.append(entry)
            cursor += audio_duration_ms + transition_ms
        return timeline

    def _subtitle_from_timeline(
        self, task_id: str, script: VideoScript, timeline: list[dict[str, object]]
    ) -> SubtitleDocument:
        items = [
            SubtitleItem(
                text=script.segments[index].voiceText,
                startMs=_int_value(item["startMs"]),
                endMs=_int_value(item["endMs"]),
                segmentIndex=index,
            )
            for index, item in enumerate(timeline)
        ]
        self.normalizer._ensure_increasing(items)
        return SubtitleDocument(taskId=task_id, level="sentence", items=items)


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    if isinstance(value, float):
        return int(value)
    return 0


def _parse_json_bytes(body: bytes) -> object:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _concat_segment_audio(
    segment_results: list[dict[str, object]], content_type: str, transition_ms: int
) -> bytes:
    audio_chunks: list[bytes] = []
    for index, item in enumerate(segment_results):
        audio_chunks.append(cast(bytes, item["audioBytes"]))
        if index < len(segment_results) - 1 and transition_ms > 0:
            audio_chunks.append(_silence_audio_bytes(content_type, transition_ms))
    if content_type == "audio/wav":
        return _concat_wav_bytes(audio_chunks)
    if content_type == "audio/mpeg":
        try:
            return _concat_with_ffmpeg(audio_chunks, ".mp3")
        except AppError:
            return b"".join(audio_chunks)
    return b"".join(audio_chunks)


def _silence_audio_bytes(content_type: str, duration_ms: int) -> bytes:
    if content_type == "audio/wav":
        sample_rate = 8_000
        frames = int(sample_rate * duration_ms / 1000)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b"\x00\x00" * frames)
        return buffer.getvalue()
    if content_type == "audio/mpeg":
        try:
            return _ffmpeg_silence_mp3(duration_ms)
        except AppError:
            return b""
    return b""


def _concat_wav_bytes(audio_chunks: list[bytes]) -> bytes:
    params: wave._wave_params | None = None
    frames: list[bytes] = []
    for chunk in audio_chunks:
        with wave.open(io.BytesIO(chunk), "rb") as wav_file:
            current = wav_file.getparams()
            if params is None:
                params = current
            elif current[:3] != params[:3]:
                raise AppError(
                    "TTS_AUDIO_CONCAT_FAILED",
                    "WAV segment parameters do not match",
                    True,
                    {},
                )
            frames.append(wav_file.readframes(wav_file.getnframes()))
    if params is None:
        return b""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setparams(params)
        output.writeframes(b"".join(frames))
    return buffer.getvalue()


def _concat_with_ffmpeg(audio_chunks: list[bytes], suffix: str) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        concat_path = tmp_path / "audio.txt"
        out_path = tmp_path / f"combined{suffix}"
        input_paths: list[Path] = []
        for index, chunk in enumerate(audio_chunks):
            path = tmp_path / f"segment_{index}{suffix}"
            path.write_bytes(chunk)
            input_paths.append(path)
        with concat_path.open("w", encoding="utf-8") as file:
            for path in input_paths:
                file.write(f"file '{path.as_posix()}'\n")
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_path),
                    "-c",
                    "copy",
                    str(out_path),
                ],
                check=True,
                capture_output=True,
                timeout=60,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise AppError(
                "TTS_AUDIO_CONCAT_FAILED",
                "FFmpeg failed to concatenate TTS segments",
                True,
                {"reason": exc.__class__.__name__},
            ) from exc
        return out_path.read_bytes()


def _ffmpeg_silence_mp3(duration_ms: int) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "silence.mp3"
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-f",
                    "lavfi",
                    "-i",
                    "anullsrc=channel_layout=mono:sample_rate=32000",
                    "-t",
                    f"{duration_ms / 1000:.3f}",
                    "-b:a",
                    "128k",
                    str(path),
                ],
                check=True,
                capture_output=True,
                timeout=30,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            raise AppError(
                "TTS_SILENCE_GENERATION_FAILED",
                "FFmpeg failed to generate transition silence",
                True,
                {"reason": exc.__class__.__name__},
            ) from exc
        return path.read_bytes()


def _audio_bytes_duration_ms(audio_bytes: bytes, content_type: str) -> int:
    suffix = _audio_suffix_for_content_type(content_type)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"audio{suffix}"
        path.write_bytes(audio_bytes)
        if content_type == "audio/wav":
            return _wav_duration_ms(path)
        if content_type == "audio/mpeg":
            return _ffprobe_duration_ms(path)
    return 0


def _wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
    if rate <= 0:
        return 0
    return int(frames / rate * 1000)


def _ffprobe_duration_ms(path: Path) -> int:
    try:
        completed = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return int(float(completed.stdout.strip()) * 1000)
    except (
        FileNotFoundError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        ValueError,
    ):
        return 0


def _audio_suffix_for_content_type(content_type: str) -> str:
    if content_type == "audio/mpeg":
        return ".mp3"
    if content_type == "audio/wav":
        return ".wav"
    if content_type == "audio/flac":
        return ".flac"
    if content_type == "audio/L16":
        return ".pcm"
    return ".audio"


def _content_type_for_audio_format(audio_format: str) -> str:
    if audio_format == "mp3":
        return "audio/mpeg"
    if audio_format == "wav":
        return "audio/wav"
    if audio_format == "flac":
        return "audio/flac"
    if audio_format == "pcm":
        return "audio/L16"
    return "application/octet-stream"


def _parse_vtt_timestamps(vtt: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    lines = [line.strip() for line in vtt.splitlines()]
    for index, line in enumerate(lines):
        if "-->" not in line:
            continue
        start_raw, end_raw = [part.strip().split(" ")[0] for part in line.split("-->", 1)]
        text = ""
        if index + 1 < len(lines):
            text = lines[index + 1].strip()
        items.append(
            {
                "text": text,
                "startMs": _vtt_time_to_ms(start_raw),
                "endMs": _vtt_time_to_ms(end_raw),
                "segmentIndex": 0,
            }
        )
    return items


def _vtt_time_to_ms(value: str) -> int:
    value = value.replace(",", ".")
    hours_raw, minutes_raw, seconds_raw = value.split(":")
    if "." in seconds_raw:
        seconds, millis = seconds_raw.split(".", 1)
    else:
        seconds = seconds_raw
        millis = "0"
    return (
        int(hours_raw) * 3_600_000
        + int(minutes_raw) * 60_000
        + int(seconds) * 1000
        + int(millis[:3].ljust(3, "0"))
    )


def _pad_wav_to_min_duration(path: Path, min_duration_ms: int) -> None:
    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        rate = wav_file.getframerate()
        frames = wav_file.readframes(wav_file.getnframes())
    current_ms = int(len(frames) / max(channels * sample_width, 1) / max(rate, 1) * 1000)
    if current_ms >= min_duration_ms:
        return
    missing_frames = int((min_duration_ms - current_ms) / 1000 * rate)
    silence = b"\x00" * missing_frames * channels * sample_width
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(rate)
        wav_file.writeframes(frames + silence)


def _pad_wav_bytes(audio_bytes: bytes, min_duration_ms: int) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "audio.wav"
        path.write_bytes(audio_bytes)
        _pad_wav_to_min_duration(path, min_duration_ms)
        return path.read_bytes()
