from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from uuid import uuid4


class LocalObjectStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.run_folder: str | None = None
        self.root.mkdir(parents=True, exist_ok=True)

    def begin_run(self, folder_name: str) -> Path:
        self.run_folder = _safe_folder_name(folder_name)
        path = self.root / self.run_folder
        path.mkdir(parents=True, exist_ok=True)
        return path

    def current_run_path(self) -> Path | None:
        if self.run_folder is None:
            return None
        return self.root / self.run_folder

    def write_bytes(self, prefix: str, suffix: str, data: bytes) -> dict[str, Any]:
        base = self.root / self.run_folder if self.run_folder else self.root
        directory = base / prefix
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{uuid4().hex}{suffix}"
        path.write_bytes(data)
        checksum = "sha256:" + hashlib.sha256(data).hexdigest()
        return {
            "url": path.resolve().as_uri(),
            "path": str(path.resolve()),
            "sizeBytes": len(data),
            "checksum": checksum,
        }

    def write_json(self, prefix: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.write_bytes(
            prefix,
            ".json",
            json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
        )

    def read_json_url(self, url: str) -> dict[str, Any]:
        payload = json.loads(self.path_from_url(url).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Stored JSON payload is not an object")
        return payload

    def path_from_url(self, url: str) -> Path:
        if url.startswith("file:///"):
            import urllib.parse

            return Path(urllib.parse.unquote(url.removeprefix("file:///")))
        return Path(url)

    def exists(self, url: str) -> bool:
        return self.path_from_url(url).exists()


def _safe_folder_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value)
