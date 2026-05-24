from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.contracts.errors import AppError
from app.contracts.schemas import Candidate, default_video_preset_payload
from app.contracts.statuses import TaskStatus, can_transition


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _loads(value: str | None, default: Any) -> Any:
    if value is None or value == "":
        return default
    return json.loads(value)


class SQLiteRepository:
    def __init__(self, database_url: str) -> None:
        self.db_path = self._path_from_url(database_url)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @staticmethod
    def _path_from_url(database_url: str) -> Path:
        if database_url == "sqlite:///:memory:":
            return Path(":memory:")
        if database_url.startswith("sqlite:///"):
            return Path(database_url.removeprefix("sqlite:///"))
        return Path(database_url)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS candidates (
                    repoFullName TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    collectedAt TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS video_tasks (
                    taskId TEXT PRIMARY KEY,
                    repoFullName TEXT NOT NULL,
                    status TEXT NOT NULL,
                    selectedBy TEXT NOT NULL,
                    scriptAssetId TEXT,
                    audioAssetId TEXT,
                    subtitleAssetId TEXT,
                    videoAssetId TEXT,
                    coverAssetId TEXT,
                    packageAssetId TEXT,
                    statusHistory TEXT NOT NULL,
                    lastError TEXT,
                    reviewDecision TEXT,
                    createdAt TEXT NOT NULL,
                    updatedAt TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assets (
                    assetId TEXT PRIMARY KEY,
                    taskId TEXT NOT NULL,
                    type TEXT NOT NULL,
                    url TEXT NOT NULL,
                    contentType TEXT NOT NULL,
                    sizeBytes INTEGER NOT NULL,
                    checksum TEXT NOT NULL,
                    metadata TEXT NOT NULL,
                    createdAt TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS publish_records (
                    recordId TEXT PRIMARY KEY,
                    taskId TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    hashtags TEXT NOT NULL,
                    publishedAt TEXT NOT NULL,
                    publishUrl TEXT,
                    operator TEXT NOT NULL,
                    createdAt TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS dedup_records (
                    repoFullName TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    taskId TEXT,
                    createdAt TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS module_run_logs (
                    logId TEXT PRIMARY KEY,
                    moduleName TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    taskId TEXT,
                    durationMs INTEGER NOT NULL,
                    success INTEGER NOT NULL,
                    errorCode TEXT,
                    artifactRefs TEXT NOT NULL,
                    createdAt TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS video_presets (
                    presetId TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    isDefault INTEGER NOT NULL,
                    createdAt TEXT NOT NULL,
                    updatedAt TEXT NOT NULL
                );
                """
            )
            self._ensure_default_video_preset(conn)

    def _ensure_default_video_preset(self, conn: sqlite3.Connection) -> None:
        row = conn.execute("SELECT presetId FROM video_presets WHERE isDefault = 1").fetchone()
        if row is not None:
            return
        now = utc_now()
        payload = default_video_preset_payload()
        conn.execute(
            """
            INSERT INTO video_presets(presetId, name, payload, isDefault, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("preset_default", str(payload["name"]), _json(payload), 1, now, now),
        )

    def _preset_from_row(self, row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["payload"] = _loads(item["payload"], {})
        item["isDefault"] = bool(item["isDefault"])
        return item

    def list_video_presets(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM video_presets
                ORDER BY isDefault DESC, updatedAt DESC
                """
            ).fetchall()
        return [self._preset_from_row(row) for row in rows]

    def get_default_video_preset(self) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM video_presets WHERE isDefault = 1").fetchone()
        if row is None:
            with self.connect() as conn:
                self._ensure_default_video_preset(conn)
            return self.get_default_video_preset()
        return self._preset_from_row(row)

    def get_video_preset(self, preset_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM video_presets WHERE presetId = ?", (preset_id,)
            ).fetchone()
        if row is None:
            raise AppError(
                "VIDEO_PRESET_NOT_FOUND",
                "Video preset not found",
                False,
                {"presetId": preset_id},
            )
        return self._preset_from_row(row)

    def upsert_video_preset(
        self,
        name: str,
        payload: dict[str, Any],
        preset_id: str | None = None,
        is_default: bool = False,
    ) -> dict[str, Any]:
        now = utc_now()
        preset_id = preset_id or f"preset_{uuid4().hex[:10]}"
        if is_default:
            with self.connect() as conn:
                conn.execute("UPDATE video_presets SET isDefault = 0 WHERE presetId != ?", (preset_id,))
                conn.execute(
                    """
                    INSERT INTO video_presets(presetId, name, payload, isDefault, createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(presetId) DO UPDATE SET
                        name = excluded.name,
                        payload = excluded.payload,
                        isDefault = excluded.isDefault,
                        updatedAt = excluded.updatedAt
                    """,
                    (preset_id, name, _json(payload), 1, now, now),
                )
        else:
            with self.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO video_presets(presetId, name, payload, isDefault, createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(presetId) DO UPDATE SET
                        name = excluded.name,
                        payload = excluded.payload,
                        updatedAt = excluded.updatedAt
                    """,
                    (preset_id, name, _json(payload), 0, now, now),
                )
        return self.get_video_preset(preset_id)

    def delete_video_preset(self, preset_id: str) -> None:
        preset = self.get_video_preset(preset_id)
        if preset["isDefault"]:
            raise AppError(
                "DEFAULT_VIDEO_PRESET_IMMUTABLE",
                "Default video preset cannot be deleted",
                False,
                {"presetId": preset_id},
            )
        with self.connect() as conn:
            conn.execute("DELETE FROM video_presets WHERE presetId = ?", (preset_id,))

    def upsert_candidates(self, candidates: Iterable[Candidate]) -> list[Candidate]:
        saved: list[Candidate] = []
        with self.connect() as conn:
            for candidate in candidates:
                candidate.collectedAt = candidate.collectedAt or utc_now()
                conn.execute(
                    """
                    INSERT INTO candidates(repoFullName, payload, collectedAt)
                    VALUES (?, ?, ?)
                    ON CONFLICT(repoFullName) DO UPDATE SET
                        payload = excluded.payload,
                        collectedAt = excluded.collectedAt
                    """,
                    (candidate.repoFullName, candidate.model_dump_json(), candidate.collectedAt),
                )
                saved.append(candidate)
        return saved

    def get_candidate(self, repo_full_name: str) -> Candidate | None:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT payload FROM candidates WHERE repoFullName = ?", (repo_full_name,)
            ).fetchone()
        return Candidate.model_validate_json(row["payload"]) if row else None

    def list_candidates(self) -> list[Candidate]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT payload FROM candidates ORDER BY collectedAt DESC"
            ).fetchall()
        return [Candidate.model_validate_json(row["payload"]) for row in rows]

    def update_candidate_scores(self, candidates: Iterable[Candidate]) -> None:
        self.upsert_candidates(candidates)

    def create_task(
        self, repo_full_name: str, selected_by: str = "system", task_id: str | None = None
    ) -> dict[str, Any]:
        now = utc_now()
        task_id = task_id or f"task_{datetime.now(UTC).strftime('%Y%m%d')}_{uuid4().hex[:8]}"
        history = [
            {"from": None, "to": TaskStatus.CREATED.value, "changedAt": now, "reason": "created"}
        ]
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO video_tasks(
                    taskId, repoFullName, status, selectedBy, statusHistory,
                    createdAt, updatedAt
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    repo_full_name,
                    TaskStatus.CREATED.value,
                    selected_by,
                    _json(history),
                    now,
                    now,
                ),
            )
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM video_tasks WHERE taskId = ?", (task_id,)).fetchone()
        if row is None:
            raise AppError("TASK_NOT_FOUND", "Task not found", False, {"taskId": task_id})
        data = dict(row)
        data["statusHistory"] = _loads(data["statusHistory"], [])
        data["lastError"] = _loads(data["lastError"], None)
        data["reviewDecision"] = _loads(data["reviewDecision"], None)
        return data

    def list_tasks(self, limit: int = 20) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM video_tasks
                ORDER BY updatedAt DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        tasks: list[dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            data["statusHistory"] = _loads(data["statusHistory"], [])
            data["lastError"] = _loads(data["lastError"], None)
            data["reviewDecision"] = _loads(data["reviewDecision"], None)
            tasks.append(data)
        return tasks

    def update_task_status(self, task_id: str, target: TaskStatus, reason: str) -> dict[str, Any]:
        task = self.get_task(task_id)
        current = TaskStatus(task["status"])
        if not can_transition(current, target):
            raise AppError(
                "INVALID_STATUS_TRANSITION",
                f"Cannot transition from {current.value} to {target.value}",
                False,
                {"taskId": task_id, "from": current.value, "to": target.value},
            )
        now = utc_now()
        history = list(task["statusHistory"])
        history.append(
            {"from": current.value, "to": target.value, "changedAt": now, "reason": reason}
        )
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE video_tasks
                SET status = ?, statusHistory = ?, updatedAt = ?
                WHERE taskId = ?
                """,
                (target.value, _json(history), now, task_id),
            )
        return self.get_task(task_id)

    def fail_task(self, task_id: str, stage: str, error: AppError) -> dict[str, Any]:
        task = self.get_task(task_id)
        now = utc_now()
        last_error = error.to_dict() | {"taskId": task_id, "stage": stage}
        current = TaskStatus(task["status"])
        history = list(task["statusHistory"])
        if current is not TaskStatus.FAILED and can_transition(current, TaskStatus.FAILED):
            history.append(
                {"from": current.value, "to": "failed", "changedAt": now, "reason": stage}
            )
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE video_tasks
                SET status = ?, statusHistory = ?, lastError = ?, updatedAt = ?
                WHERE taskId = ?
                """,
                (TaskStatus.FAILED.value, _json(history), _json(last_error), now, task_id),
            )
        return self.get_task(task_id)

    def set_task_asset(self, task_id: str, asset_type: str, asset_id: str) -> None:
        column_by_type = {
            "script": "scriptAssetId",
            "audio": "audioAssetId",
            "subtitle": "subtitleAssetId",
            "video": "videoAssetId",
            "cover": "coverAssetId",
            "package": "packageAssetId",
        }
        column = column_by_type.get(asset_type)
        if column is None:
            return
        with self.connect() as conn:
            conn.execute(
                f"UPDATE video_tasks SET {column} = ?, updatedAt = ? WHERE taskId = ?",
                (asset_id, utc_now(), task_id),
            )

    def add_asset(
        self,
        task_id: str,
        asset_type: str,
        url: str,
        content_type: str,
        size_bytes: int,
        checksum: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        asset_id = f"asset_{asset_type}_{uuid4().hex[:10]}"
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO assets(
                    assetId, taskId, type, url, contentType,
                    sizeBytes, checksum, metadata, createdAt
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    task_id,
                    asset_type,
                    url,
                    content_type,
                    size_bytes,
                    checksum,
                    _json(metadata or {}),
                    now,
                ),
            )
        self.set_task_asset(task_id, asset_type, asset_id)
        return self.get_asset(asset_id)

    def get_asset(self, asset_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM assets WHERE assetId = ?", (asset_id,)).fetchone()
        if row is None:
            raise AppError("ASSET_NOT_FOUND", "Asset not found", False, {"assetId": asset_id})
        data = dict(row)
        data["metadata"] = _loads(data["metadata"], {})
        return data

    def list_assets(self, task_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM assets WHERE taskId = ? ORDER BY createdAt", (task_id,)
            ).fetchall()
        assets: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["metadata"] = _loads(item["metadata"], {})
            assets.append(item)
        return assets

    def add_dedup_record(
        self, repo_full_name: str, action: str, task_id: str | None = None
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO dedup_records(repoFullName, action, taskId, createdAt)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(repoFullName) DO UPDATE SET
                    action = excluded.action,
                    taskId = excluded.taskId,
                    createdAt = excluded.createdAt
                """,
                (repo_full_name, action, task_id, utc_now()),
            )

    def is_deduped(self, repo_full_name: str) -> bool:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM dedup_records
                WHERE repoFullName = ?
                  AND action IN ('generated','skipped','abandoned')
                """,
                (repo_full_name,),
            ).fetchone()
        return row is not None

    def add_publish_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        forbidden = {"password", "passwd", "accountPassword", "platformPassword", "token", "secret"}
        if forbidden.intersection(payload):
            raise AppError(
                "FORBIDDEN_CREDENTIAL_FIELD",
                "Platform credentials must not be stored",
                False,
                {"fields": sorted(forbidden.intersection(payload))},
            )
        record_id = f"pub_{uuid4().hex[:10]}"
        now = utc_now()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO publish_records(
                    recordId, taskId, platform, title, description, hashtags,
                    publishedAt, publishUrl, operator, createdAt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    payload["taskId"],
                    payload["platform"],
                    payload["title"],
                    payload["description"],
                    _json(payload.get("hashtags", [])),
                    payload["publishedAt"],
                    payload.get("publishUrl"),
                    payload["operator"],
                    now,
                ),
            )
        return self.get_publish_record(record_id)

    def get_publish_record(self, record_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM publish_records WHERE recordId = ?", (record_id,)
            ).fetchone()
        if row is None:
            raise AppError(
                "PUBLISH_RECORD_NOT_FOUND",
                "Publish record not found",
                False,
                {"recordId": record_id},
            )
        data = dict(row)
        data["hashtags"] = _loads(data["hashtags"], [])
        return data

    def list_publish_records(self, task_id: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM publish_records WHERE taskId = ?", (task_id,)
            ).fetchall()
        records: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["hashtags"] = _loads(item["hashtags"], [])
            records.append(item)
        return records

    def add_run_log(
        self,
        module_name: str,
        stage: str,
        success: bool,
        duration_ms: int = 0,
        task_id: str | None = None,
        error_code: str | None = None,
        artifact_refs: dict[str, Any] | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO module_run_logs(
                    logId, moduleName, stage, taskId, durationMs, success,
                    errorCode, artifactRefs, createdAt
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"log_{uuid4().hex[:10]}",
                    module_name,
                    stage,
                    task_id,
                    duration_ms,
                    int(success),
                    error_code,
                    _json(artifact_refs or {}),
                    utc_now(),
                ),
            )
