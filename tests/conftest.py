from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import Services, create_app, create_services


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        object_storage_dir=tmp_path / "objects",
        github_provider="mock",
        model_provider="mock",
        tts_provider="mock",
        render_provider="fake",
    )


@pytest.fixture()
def services(settings: Settings) -> Services:
    return create_services(settings)


@pytest.fixture()
def client(services: Services) -> TestClient:
    return TestClient(create_app(services))
