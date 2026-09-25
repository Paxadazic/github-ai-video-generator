"""Test mmx CLI TTS with Token Plan Key (sk-cp-...)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.minimax_cli import MiniMaxCliRunner  # noqa: E402
from app.tts_subtitle import MiniMaxCliTTSAdapter  # noqa: E402


def main() -> int:
    transcript = "大家好，欢迎收看今天的科技新闻。人工智能正在深刻改变我们的生活方式。"
    voice = "default_cn_tech"

    print("=" * 60)
    print("Testing mmx CLI TTS with Token Plan")
    print("=" * 60)
    print(f"Transcript: {transcript}")
    print(f"Voice: {voice}")
    print()

    # Detect current auth method
    runner = MiniMaxCliRunner(
        cli_path=os.environ.get("MINIMAX_CLI_PATH", "mmx"),
        region=os.environ.get("MINIMAX_CLI_REGION", "cn"),
        runtime_tmp_dir=Path("data/runtime_tmp"),
        timeout=180,
    )

    # Check auth status
    try:
        auth_result = runner.run_json(["auth", "status"])
        method = auth_result.get("method", "unknown")
        source = auth_result.get("source", "unknown")
        key_preview = auth_result.get("key", "")
        print(f"Current auth method: {method}")
        print(f"Key source: {source}")
        print(f"Key preview: {key_preview}")
        print()

        if method == "api-key" and "api" in key_preview.lower():
            print("WARNING: You are using a Pay-as-you-go API Key (sk-api-...).")
            print("Token Plan requires a Token Plan Key (sk-cp-...).")
            print("Please run: mmx auth login --api-key sk-cp-xxxxx")
            print()
            return 1
    except Exception as exc:
        print(f"Could not check auth status: {exc}")
        return 1

    adapter = MiniMaxCliTTSAdapter(
        runner=runner,
        model="speech-2.8-hd",
        voice_id=None,
        timeout=180,
    )

    try:
        result = adapter.synthesize(transcript, voice)
    except Exception as exc:
        print(f"FAILED: {exc}")
        return 1

    audio_bytes = result["audioBytes"]
    content_type = result["contentType"]
    duration_ms = result["durationMs"]
    resolved_voice = result["voice"]

    print("SUCCESS!")
    print(f"  Resolved voice : {resolved_voice}")
    print(f"  Content type   : {content_type}")
    print(f"  Duration (ms)  : {duration_ms}")
    print(f"  Audio size     : {len(audio_bytes)} bytes")

    output_path = Path("data/runtime_tmp/test_mmx_tts_output.mp3")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(audio_bytes)
    print(f"  Saved to       : {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
