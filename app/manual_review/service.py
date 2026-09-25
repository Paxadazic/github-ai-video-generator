from __future__ import annotations

from app.contracts.errors import AppError
from app.contracts.statuses import TaskStatus
from app.storage.repository import SQLiteRepository, utc_now

ALLOWED_RETRY_ACTIONS = {
    "regenerate_title_description",
    "regenerate_script",
    "regenerate_tts",
    "rerender_video",
    "abandon_and_select_next",
}


class ManualReviewService:
    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    def get_review_detail(self, task_id: str) -> dict[str, object]:
        task = self.repository.get_task(task_id)
        candidate = self.repository.get_candidate(str(task["repoFullName"]))
        assets = self.repository.list_assets(task_id)
        by_type = {asset["type"]: asset for asset in assets}
        return {
            "taskId": task_id,
            "repoUrl": candidate.repoUrl if candidate else "",
            "recommendReason": candidate.recommendReason if candidate else "",
            "riskFlags": candidate.riskFlags if candidate else [],
            "videoUrl": by_type.get("video", {}).get("url"),
            "coverUrl": by_type.get("cover", {}).get("url"),
            "scriptUrl": by_type.get("script", {}).get("url"),
            "audioUrl": by_type.get("audio", {}).get("url"),
            "subtitleUrl": by_type.get("subtitle", {}).get("url"),
            "title": by_type.get("script", {}).get("metadata", {}).get("title", ""),
            "description": candidate.description if candidate else "",
            "hashtags": [],
        }

    def decide(
        self,
        task_id: str,
        decision: str,
        comment: str = "",
        retry_action: str | None = None,
        reviewer: str = "manual",
    ) -> dict[str, object]:
        task = self.repository.get_task(task_id)
        if task["status"] != TaskStatus.REVIEW_PENDING.value:
            raise AppError(
                "REVIEW_STATUS_INVALID",
                "Task must be review_pending before review decision",
                False,
                {"taskId": task_id, "status": task["status"]},
            )
        if decision == "approved":
            updated = self.repository.update_task_status(
                task_id, TaskStatus.APPROVED, "manual review approved"
            )
        elif decision == "rejected":
            if retry_action not in ALLOWED_RETRY_ACTIONS:
                raise AppError(
                    "INVALID_RETRY_ACTION",
                    "Retry action is not allowed",
                    False,
                    {"retryAction": retry_action},
                )
            updated = self.repository.update_task_status(
                task_id, TaskStatus.REJECTED, comment or "manual review rejected"
            )
        else:
            raise AppError(
                "INVALID_REVIEW_DECISION",
                "Review decision must be approved or rejected",
                False,
                {"decision": decision},
            )
        self.repository.add_run_log(
            "manual_review",
            "decision",
            True,
            task_id=task_id,
            artifact_refs={
                "decision": decision,
                "comment": comment,
                "retryAction": retry_action,
                "reviewer": reviewer,
                "reviewedAt": utc_now(),
            },
        )
        return {"taskId": task_id, "status": updated["status"], "retryAction": retry_action}
