from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from app.contracts.errors import AppError
from app.contracts.statuses import TaskStatus
from app.storage.object_store import LocalObjectStore
from app.storage.repository import SQLiteRepository

PLATFORM_NOTES = {
    "douyin": "Manual upload; verify title and cover before publishing.",
    "wechat_channels": "Manual upload through official app or console.",
    "bilibili": "Manual upload; choose tech/open-source category.",
    "xiaohongshu": "Manual upload; adapt tags and cover text.",
}


class PublishLedgerService:
    def __init__(self, repository: SQLiteRepository, object_store: LocalObjectStore) -> None:
        self.repository = repository
        self.object_store = object_store

    def export_package(self, task_id: str, platforms: list[str]) -> dict[str, object]:
        task = self.repository.get_task(task_id)
        if task["status"] != TaskStatus.APPROVED.value:
            raise AppError(
                "PUBLISH_REQUIRES_APPROVAL",
                "Only approved tasks can export publish packages",
                False,
                {"taskId": task_id, "status": task["status"]},
            )
        candidate = self.repository.get_candidate(str(task["repoFullName"]))
        assets = {asset["type"]: asset for asset in self.repository.list_assets(task_id)}
        script_asset = assets.get("script")
        video_asset = assets.get("video")
        cover_asset = assets.get("cover")
        if not script_asset or not video_asset or not cover_asset:
            raise AppError(
                "PUBLISH_ASSET_MISSING",
                "Publish package requires script, video, and cover",
                False,
                {"taskId": task_id},
            )
        script = self.object_store.read_json_url(str(script_asset["url"]))
        items = {
            "videoUrl": video_asset["url"],
            "coverUrl": cover_asset["url"],
            "title": script["title"],
            "description": script["description"],
            "hashtags": script["hashtags"],
            "repoUrl": candidate.repoUrl if candidate else "",
            "recommendedPublishTime": datetime.now(UTC)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z"),
            "platformNotes": {
                platform: PLATFORM_NOTES.get(platform, "Manual publish only.")
                for platform in platforms
            },
        }
        manifest = {"taskId": task_id, "items": items}
        written = self.object_store.write_bytes(
            "packages", ".json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        )
        package_asset = self.repository.add_asset(
            task_id,
            "package",
            str(written["url"]),
            "application/json",
            int(written["sizeBytes"]),
            str(written["checksum"]),
            {"platforms": platforms},
        )
        self.repository.add_run_log("publish_ledger", "export_package", True, task_id=task_id)
        return {"taskId": task_id, "packageUrl": package_asset["url"], "items": items}

    def create_publish_record(self, payload: dict[str, Any]) -> dict[str, object]:
        task = self.repository.get_task(str(payload["taskId"]))
        if task["status"] != TaskStatus.APPROVED.value:
            raise AppError(
                "PUBLISH_RECORD_REQUIRES_APPROVAL",
                "Only approved tasks can be recorded as manually published",
                False,
                {"taskId": payload["taskId"], "status": task["status"]},
            )
        for required in ("taskId", "platform", "publishedAt", "operator", "title", "description"):
            if not payload.get(required):
                raise AppError(
                    "PUBLISH_RECORD_INVALID",
                    "Publish record missing required field",
                    False,
                    {"field": required},
                )
        record = self.repository.add_publish_record(payload)
        self.repository.update_task_status(
            str(payload["taskId"]), TaskStatus.PUBLISHED_MANUAL, "manual publish recorded"
        )
        self.repository.add_dedup_record(
            str(task["repoFullName"]), "generated", str(payload["taskId"])
        )
        self.repository.add_run_log(
            "publish_ledger", "publish_record", True, task_id=str(payload["taskId"])
        )
        return {"record": record, "status": TaskStatus.PUBLISHED_MANUAL.value}
