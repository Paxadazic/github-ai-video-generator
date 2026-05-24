from __future__ import annotations

from typing import Any, cast

import pytest

from app.contracts.errors import AppError
from app.contracts.statuses import TaskStatus
from app.main import Services
from tests.helpers import candidate, script_payload


def _approved_task_with_assets(services: Services) -> str:
    services.repository.upsert_candidates([candidate("owner/project")])
    task = services.repository.create_task("owner/project")
    task_id = str(task["taskId"])
    for status in [
        TaskStatus.COLLECTED,
        TaskStatus.SCORED,
        TaskStatus.SCRIPT_GENERATED,
        TaskStatus.TTS_GENERATED,
        TaskStatus.RENDERING,
        TaskStatus.RENDERED,
        TaskStatus.REVIEW_PENDING,
    ]:
        services.repository.update_task_status(task_id, status, status.value)
    script = services.object_store.write_json("scripts", script_payload())
    services.repository.add_asset(
        task_id,
        "script",
        script["url"],
        "application/json",
        script["sizeBytes"],
        script["checksum"],
        {"title": "Project"},
    )
    video = services.object_store.write_json(
        "videos", {"metadata": {"durationSec": 65, "width": 1080, "height": 1920}}
    )
    services.repository.add_asset(
        task_id,
        "video",
        video["url"],
        "video/mp4",
        video["sizeBytes"],
        video["checksum"],
        {"durationSec": 65},
    )
    cover = services.object_store.write_bytes("covers", ".png", b"cover")
    services.repository.add_asset(
        task_id, "cover", cover["url"], "image/png", cover["sizeBytes"], cover["checksum"], {}
    )
    services.review.decide(task_id, "approved", "ok")
    return task_id


def test_review_detail_decision_and_invalid_retry(services: Services) -> None:
    services.repository.upsert_candidates([candidate("owner/project")])
    task = services.repository.create_task("owner/project")
    services.repository.update_task_status(task["taskId"], TaskStatus.COLLECTED, "x")
    services.repository.update_task_status(task["taskId"], TaskStatus.SCORED, "x")
    services.repository.update_task_status(task["taskId"], TaskStatus.SCRIPT_GENERATED, "x")
    services.repository.update_task_status(task["taskId"], TaskStatus.TTS_GENERATED, "x")
    services.repository.update_task_status(task["taskId"], TaskStatus.RENDERING, "x")
    services.repository.update_task_status(task["taskId"], TaskStatus.RENDERED, "x")
    services.repository.update_task_status(task["taskId"], TaskStatus.REVIEW_PENDING, "x")
    detail = services.review.get_review_detail(task["taskId"])
    assert detail["repoUrl"] == "https://github.com/owner/project"
    with pytest.raises(AppError):
        services.review.decide(task["taskId"], "rejected", "bad", "not_allowed")
    result = services.review.decide(task["taskId"], "rejected", "bad", "regenerate_script")
    assert result["status"] == "rejected"


def test_publish_requires_approval_and_rejects_credentials(services: Services) -> None:
    task = services.repository.create_task("owner/project")
    with pytest.raises(AppError):
        services.publish.export_package(task["taskId"], ["douyin"])

    task_id = _approved_task_with_assets(services)
    package = services.publish.export_package(
        task_id, ["douyin", "wechat_channels", "bilibili", "xiaohongshu"]
    )
    items = cast(dict[str, Any], package["items"])
    notes = cast(dict[str, str], items["platformNotes"])
    assert notes["douyin"]
    with pytest.raises(AppError):
        services.publish.create_publish_record(
            {
                "taskId": task_id,
                "platform": "douyin",
                "title": "x",
                "description": "x",
                "hashtags": [],
                "publishedAt": "2026-05-22T12:00:00Z",
                "operator": "manual",
                "password": "forbidden",
            }
        )
    record = services.publish.create_publish_record(
        {
            "taskId": task_id,
            "platform": "douyin",
            "title": "x",
            "description": "x",
            "hashtags": ["GitHub"],
            "publishedAt": "2026-05-22T12:00:00Z",
            "publishUrl": "https://example.com/video",
            "operator": "manual",
        }
    )
    assert record["status"] == "published_manual"
