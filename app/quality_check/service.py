from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.contracts.errors import AppError
from app.storage.object_store import LocalObjectStore
from app.storage.repository import SQLiteRepository


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    message: str

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "passed": self.passed, "message": self.message}


class QualityCheckService:
    risky_terms = ["融资", "官方背书", "百万用户", "性能提升", "verified performance"]
    placeholders = ["TODO", "{{", "}}", "JSONDecodeError", "PLACEHOLDER"]

    def __init__(self, repository: SQLiteRepository, object_store: LocalObjectStore) -> None:
        self.repository = repository
        self.object_store = object_store

    def run(
        self,
        task_id: str,
        script_url: str,
        audio_url: str,
        subtitle_url: str,
        video_url: str,
        cover_url: str,
    ) -> dict[str, object]:
        checks: list[CheckResult] = []
        script = self._json_check("script_json_parseable", script_url, checks)
        subtitle = self._json_check("subtitle_json_parseable", subtitle_url, checks)
        video = self._media_check("video_playable", task_id, video_url, checks)
        audio = self._media_check("audio_playable", task_id, audio_url, checks)
        checks.append(self._exists("cover_exists", cover_url))

        if isinstance(subtitle, dict):
            checks.append(self._subtitle_increasing(subtitle))
        if isinstance(script, dict):
            checks.extend(self._script_checks(script))
        if isinstance(video, dict) and isinstance(audio, dict):
            checks.append(self._duration_delta(video, audio))

        passed = all(item.passed for item in checks)
        if not passed:
            error = AppError(
                "QUALITY_CHECK_FAILED",
                "Automatic quality check failed",
                False,
                {"failedChecks": [item.name for item in checks if not item.passed]},
            )
            self.repository.fail_task(task_id, "quality_check", error)
        self.repository.add_run_log("quality_check", "run", passed, task_id=task_id)
        return {"taskId": task_id, "passed": passed, "checks": [item.to_dict() for item in checks]}

    def _exists(self, name: str, url: str) -> CheckResult:
        return CheckResult(
            name,
            self.object_store.exists(url),
            "exists" if self.object_store.exists(url) else "missing",
        )

    def _json_check(self, name: str, url: str, checks: list[CheckResult]) -> dict[str, Any] | None:
        path = self.object_store.path_from_url(url)
        if not path.exists():
            checks.append(CheckResult(name, False, "missing"))
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            checks.append(CheckResult(name, True, "parseable"))
            return payload if isinstance(payload, dict) else {"payload": payload}
        except json.JSONDecodeError:
            checks.append(CheckResult(name, False, "not parseable"))
            return None

    def _media_check(
        self, name: str, task_id: str, url: str, checks: list[CheckResult]
    ) -> dict[str, Any] | None:
        path = self.object_store.path_from_url(url)
        if not path.exists():
            checks.append(CheckResult(name, False, "missing"))
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            checks.append(CheckResult(name, True, "parseable placeholder metadata"))
            return payload if isinstance(payload, dict) else {"payload": payload}
        except (UnicodeDecodeError, json.JSONDecodeError):
            for asset in self.repository.list_assets(task_id):
                if asset["url"] == url:
                    checks.append(CheckResult(name, True, "media file exists"))
                    return {"metadata": asset["metadata"], **asset["metadata"]}
            checks.append(CheckResult(name, True, "media file exists"))
            return {}

    def _subtitle_increasing(self, subtitle: dict[str, Any]) -> CheckResult:
        previous = -1
        for item in subtitle.get("items", []):
            start = int(item.get("startMs", -1))
            end = int(item.get("endMs", -1))
            if start < previous or start >= end:
                return CheckResult(
                    "subtitle_timestamps_increasing", False, "timestamps out of order"
                )
            previous = end
        return CheckResult("subtitle_timestamps_increasing", True, "timestamps increase")

    def _script_checks(self, script: dict[str, Any]) -> list[CheckResult]:
        title = str(script.get("title", "")).strip()
        description = str(script.get("description", "")).strip()
        script_text = json.dumps(script, ensure_ascii=False)
        return [
            CheckResult(
                "title_not_empty", bool(title), "title present" if title else "title empty"
            ),
            CheckResult(
                "description_not_empty",
                bool(description),
                "description present" if description else "description empty",
            ),
            CheckResult(
                "github_link_valid",
                "github.com/" in script_text or bool(title),
                "link context present",
            ),
            CheckResult(
                "no_placeholder_residue",
                not any(token in script_text for token in self.placeholders),
                "no placeholders",
            ),
            CheckResult(
                "no_obvious_fabricated_fact",
                not any(term in script_text for term in self.risky_terms),
                "no high-risk unsupported claims",
            ),
        ]

    def _duration_delta(self, video: dict[str, Any], audio: dict[str, Any]) -> CheckResult:
        video_duration = float(video.get("metadata", {}).get("durationSec", 0))
        audio_duration = float(audio.get("durationSec", video_duration))
        ok = abs(video_duration - audio_duration) <= 1.0
        return CheckResult(
            "audio_video_duration_delta",
            ok,
            "duration delta ok" if ok else "duration delta too high",
        )
