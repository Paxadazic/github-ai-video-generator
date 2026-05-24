from __future__ import annotations

from app.contracts.errors import AppError
from app.contracts.responses import error_response, success_response
from app.contracts.statuses import TaskStatus, can_transition


def test_response_contract_success_and_error() -> None:
    ok = success_response({"value": 1}, "req_001")
    assert ok == {"success": True, "requestId": "req_001", "data": {"value": 1}, "error": None}

    err = error_response(
        AppError("FAIL", "failed", True, {"api_key": "secret", "nested": {"token": "hidden"}}),
        "req_002",
    )
    assert err["success"] is False
    assert err["data"] is None
    assert err["error"]["detail"]["api_key"] == "[REDACTED]"
    assert err["error"]["detail"]["nested"]["token"] == "[REDACTED]"


def test_task_status_transitions_are_explicit() -> None:
    assert can_transition(TaskStatus.CREATED, TaskStatus.COLLECTED)
    assert can_transition(TaskStatus.APPROVED, TaskStatus.PUBLISHED_MANUAL)
    assert not can_transition(TaskStatus.CREATED, TaskStatus.PUBLISHED_MANUAL)
    assert not can_transition(TaskStatus.PUBLISHED_MANUAL, TaskStatus.FAILED)
