from __future__ import annotations

import pytest

from app.contracts.errors import AppError
from app.contracts.statuses import TaskStatus
from app.main import Services
from tests.helpers import candidate


def test_candidate_upsert_task_status_asset_publish_and_dedup(services: Services) -> None:
    repo = services.repository
    first = candidate("owner/tool", stars=100)
    second = candidate("owner/tool", stars=200)
    repo.upsert_candidates([first])
    repo.upsert_candidates([second])
    assert repo.get_candidate("owner/tool").stars == 200

    task = repo.create_task("owner/tool")
    task_id = task["taskId"]
    assert task["status"] == "created"
    task = repo.update_task_status(task_id, TaskStatus.COLLECTED, "collected")
    assert task["statusHistory"][-1]["to"] == "collected"

    asset = repo.add_asset(
        task_id, "script", "file:///tmp/script.json", "application/json", 2, "sha256:x", {}
    )
    assert repo.get_asset(asset["assetId"])["taskId"] == task_id
    assert repo.list_assets(task_id)[0]["type"] == "script"

    repo.add_dedup_record("owner/tool", "generated", task_id)
    assert repo.is_deduped("owner/tool")
    repo.add_run_log("storage", "test", True, task_id=task_id)


def test_illegal_transition_and_failure_preserve_context(services: Services) -> None:
    repo = services.repository
    task = repo.create_task("owner/tool")
    with pytest.raises(AppError) as exc:
        repo.update_task_status(task["taskId"], TaskStatus.PUBLISHED_MANUAL, "bad")
    assert exc.value.detail["taskId"] == task["taskId"]

    failed = repo.fail_task(task["taskId"], "unit", AppError("BROKEN", "broken", True, {"x": 1}))
    assert failed["status"] == "failed"
    assert failed["lastError"]["taskId"] == task["taskId"]
    assert failed["lastError"]["stage"] == "unit"
