from __future__ import annotations

from fastapi.testclient import TestClient

from app.contracts.errors import AppError
from app.contracts.statuses import TaskStatus
from app.main import Services
from tests.helpers import candidate, script_payload


def test_core_api_envelope(client: TestClient) -> None:
    response = client.post("/api/jobs/collect-github-daily", json={"limit": 1})
    body = response.json()
    assert body["success"] is True
    assert body["requestId"].startswith("req_")
    assert "candidates" in body["data"]
    assert body["error"] is None

    bad = client.post("/api/jobs/collect-github-daily", json={"since": "weekly"})
    bad_body = bad.json()
    assert bad_body["success"] is False
    assert bad_body["data"] is None
    assert bad_body["error"]["code"] == "INVALID_TRENDING_SINCE"


def test_workbench_page_contains_static_mount_points(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert 'id="workbench"' in response.text
    assert 'id="generate"' in response.text
    assert 'id="recentTasks"' in response.text
    assert "renderError(error)" in response.text
    assert 'id="discoverBtn"' in response.text
    assert 'id="repoInput"' in response.text
    assert 'id="candidatePanel"' in response.text


def test_discover_api_returns_recommended_candidates(client: TestClient) -> None:
    response = client.post("/api/discover", json={"candidateLimit": 3})
    body = response.json()
    assert body["success"] is True
    assert "recommended" in body["data"]
    assert isinstance(body["data"]["recommended"], list)
    assert len(body["data"]["recommended"]) > 0
    first = body["data"]["recommended"][0]
    assert "repoFullName" in first
    assert "score" in first
    assert "recommendReason" in first
    assert "repoUrl" in first
    assert "riskFlags" in first


def test_recent_tasks_detail_and_asset_proxy(client: TestClient, services: Services) -> None:
    services.repository.upsert_candidates([candidate("owner/project")])
    task = services.repository.create_task("owner/project")
    task_id = str(task["taskId"])
    services.repository.update_task_status(task_id, TaskStatus.COLLECTED, "collected")
    script = services.object_store.write_json("scripts", script_payload())
    video = services.object_store.write_bytes("videos", ".mp4", b"fake mp4")
    services.repository.add_asset(
        task_id,
        "script",
        str(script["url"]),
        "application/json",
        int(script["sizeBytes"]),
        str(script["checksum"]),
        {"title": "Project is trending"},
    )
    video_asset = services.repository.add_asset(
        task_id,
        "video",
        str(video["url"]),
        "video/mp4",
        int(video["sizeBytes"]),
        str(video["checksum"]),
        {"durationSec": 65},
    )

    recent = client.get("/api/tasks/recent?limit=20").json()
    assert recent["success"] is True
    assert recent["data"]["tasks"][0]["taskId"] == task_id
    assert recent["data"]["tasks"][0]["assets"]["video"]["contentUrl"].endswith("/content")

    detail = client.get(f"/api/tasks/{task_id}").json()
    assert detail["success"] is True
    assert detail["data"]["task"]["repoFullName"] == "owner/project"
    assert detail["data"]["assetsByType"]["script"]["contentType"] == "application/json"
    assert detail["data"]["review"]["videoUrl"] == video_asset["url"]
    assert detail["data"]["publishRecords"] == []

    content = client.get(f"/api/assets/{video_asset['assetId']}/content")
    assert content.status_code == 200
    assert content.headers["content-type"].startswith("video/mp4")
    assert content.content == b"fake mp4"


def test_recent_tasks_include_last_error_and_missing_asset_error(
    client: TestClient, services: Services
) -> None:
    task = services.repository.create_task("owner/broken")
    task_id = str(task["taskId"])
    services.repository.fail_task(
        task_id,
        "quality_check",
        AppError("QUALITY_CHECK_FAILED", "Automatic quality check failed", False, {}),
    )
    missing_asset = services.repository.add_asset(
        task_id,
        "video",
        "file:///C:/tmp/not-registered-output.mp4",
        "video/mp4",
        0,
        "sha256:missing",
        {},
    )

    recent = client.get("/api/tasks/recent").json()
    assert recent["data"]["tasks"][0]["lastError"]["code"] == "QUALITY_CHECK_FAILED"
    assert recent["data"]["tasks"][0]["lastError"]["stage"] == "quality_check"

    missing = client.get(f"/api/assets/{missing_asset['assetId']}/content").json()
    assert missing["success"] is False
    assert missing["error"]["code"] == "ASSET_CONTENT_NOT_FOUND"

    unknown = client.get("/api/assets/asset_unknown/content").json()
    assert unknown["success"] is False
    assert unknown["error"]["code"] == "ASSET_NOT_FOUND"
