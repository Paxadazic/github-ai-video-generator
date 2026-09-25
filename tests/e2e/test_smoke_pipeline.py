from __future__ import annotations

from typing import Any, cast

import pytest

from app.contracts.errors import AppError
from app.contracts.statuses import TaskStatus
from app.main import Services


def test_offline_pipeline_to_review_then_manual_publish(services: Services) -> None:
    result = services.control.run_to_review_pending()
    task_id = str(result["taskId"])
    task = services.repository.get_task(task_id)
    assert task["status"] == "review_pending"
    assert [item["to"] for item in task["statusHistory"]] == [
        "created",
        "collected",
        "scored",
        "script_generated",
        "tts_generated",
        "rendering",
        "rendered",
        "review_pending",
    ]
    recommended = cast(list[dict[str, Any]], result["recommended"])
    assert len(recommended) >= 3
    assert len(services.repository.list_assets(task_id)) >= 5

    with pytest.raises(AppError):
        other = services.repository.create_task("owner/not-approved")
        services.publish.export_package(other["taskId"], ["douyin"])

    published = services.control.approve_export_and_record(task_id)
    assert published["task"]["status"] == "published_manual"
    assert published["publishRecord"]["status"] == "published_manual"
    assert services.repository.list_publish_records(task_id)
    assert services.repository.is_deduped(task["repoFullName"])


def test_control_plane_failure_records_error(services: Services) -> None:
    services.tts.adapter.fail = True
    with pytest.raises(AppError):
        services.control.run_to_review_pending()
    tasks = services.repository.connect().execute("SELECT taskId FROM video_tasks").fetchall()
    assert tasks
    task = services.repository.get_task(tasks[-1]["taskId"])
    assert task["status"] == TaskStatus.FAILED.value
    assert task["lastError"]["stage"] in {"tts_subtitle", "control_plane"}
