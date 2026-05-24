from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SENSITIVE_KEYS = {"password", "passwd", "secret", "token", "api_key", "apikey", "authorization"}


def sanitize_detail(detail: dict[str, Any] | None) -> dict[str, Any]:
    if not detail:
        return {}
    sanitized: dict[str, Any] = {}
    for key, value in detail.items():
        lowered = key.lower()
        if any(secret in lowered for secret in SENSITIVE_KEYS):
            sanitized[key] = "[REDACTED]"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_detail(value)
        else:
            sanitized[key] = value
    return sanitized


@dataclass
class AppError(Exception):
    code: str
    message: str
    retryable: bool
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "detail": sanitize_detail(self.detail),
        }
