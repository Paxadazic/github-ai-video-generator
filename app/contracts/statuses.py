from __future__ import annotations

from enum import StrEnum


class TaskStatus(StrEnum):
    CREATED = "created"
    COLLECTED = "collected"
    SCORED = "scored"
    SCRIPT_GENERATED = "script_generated"
    TTS_GENERATED = "tts_generated"
    RENDERING = "rendering"
    RENDERED = "rendered"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED_MANUAL = "published_manual"
    FAILED = "failed"


ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.CREATED: {
        TaskStatus.COLLECTED,
        TaskStatus.SCORED,
        TaskStatus.SCRIPT_GENERATED,
        TaskStatus.FAILED,
    },
    TaskStatus.COLLECTED: {TaskStatus.SCORED, TaskStatus.FAILED},
    TaskStatus.SCORED: {TaskStatus.SCRIPT_GENERATED, TaskStatus.FAILED},
    TaskStatus.SCRIPT_GENERATED: {TaskStatus.TTS_GENERATED, TaskStatus.FAILED},
    TaskStatus.TTS_GENERATED: {TaskStatus.RENDERING, TaskStatus.FAILED},
    TaskStatus.RENDERING: {TaskStatus.RENDERED, TaskStatus.FAILED},
    TaskStatus.RENDERED: {TaskStatus.REVIEW_PENDING, TaskStatus.FAILED},
    TaskStatus.REVIEW_PENDING: {TaskStatus.APPROVED, TaskStatus.REJECTED, TaskStatus.FAILED},
    TaskStatus.APPROVED: {TaskStatus.PUBLISHED_MANUAL, TaskStatus.FAILED},
    TaskStatus.REJECTED: {
        TaskStatus.SCORED,
        TaskStatus.SCRIPT_GENERATED,
        TaskStatus.TTS_GENERATED,
        TaskStatus.RENDERING,
        TaskStatus.FAILED,
    },
    TaskStatus.PUBLISHED_MANUAL: set(),
    TaskStatus.FAILED: set(),
}


def can_transition(current: TaskStatus, target: TaskStatus) -> bool:
    return target in ALLOWED_TRANSITIONS[current]
