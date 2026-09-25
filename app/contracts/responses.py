from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.contracts.errors import AppError


def new_request_id() -> str:
    return f"req_{uuid4().hex[:12]}"


@dataclass(frozen=True)
class ApiResponse:
    success: bool
    requestId: str
    data: dict[str, Any] | None
    error: dict[str, Any] | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "requestId": self.requestId,
            "data": self.data,
            "error": self.error,
        }


def success_response(data: dict[str, Any], request_id: str | None = None) -> dict[str, Any]:
    return ApiResponse(True, request_id or new_request_id(), data, None).to_dict()


def error_response(error: AppError, request_id: str | None = None) -> dict[str, Any]:
    return ApiResponse(False, request_id or new_request_id(), None, error.to_dict()).to_dict()
