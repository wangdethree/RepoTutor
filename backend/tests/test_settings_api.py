from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api import routes
from app.llm import client as llm_client_module
from app.main import app
from app.repositories.sqlite_repository import SQLiteRepository


def test_llm_settings_can_be_saved_without_leaking_api_key(tmp_path: Path, monkeypatch) -> None:
    test_repository = SQLiteRepository(f"sqlite:///{tmp_path / 'settings.db'}")
    monkeypatch.setattr(routes, "repository", test_repository)
    client = TestClient(app)
    payload = {
        "base_url": "https://example.com/v1",
        "model": "demo-model",
        "temperature": 0.3,
        "api_key": "sk-test-secret-value",
    }

    response = client.put("/api/settings/llm", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["api_key_configured"] is True
    assert data["api_key_masked"] == "sk-t...alue"
    assert "sk-test-secret-value" not in response.text
    assert data["base_url"] == "https://example.com/v1"
    assert data["model"] == "demo-model"
    assert data["temperature"] == 0.3

    monkeypatch.setattr(llm_client_module, "SQLiteRepository", lambda: test_repository)
    llm_client = llm_client_module.LLMClient()

    assert llm_client.api_key == "sk-test-secret-value"
    assert llm_client.base_url == "https://example.com/v1"
    assert llm_client.model == "demo-model"
    assert llm_client.temperature == 0.3
