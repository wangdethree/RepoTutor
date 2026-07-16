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


def test_health_and_capabilities_report_runtime_status(tmp_path: Path, monkeypatch) -> None:
    test_repository = SQLiteRepository(f"sqlite:///{tmp_path / 'health.db'}")
    monkeypatch.setattr(routes, "repository", test_repository)
    client = TestClient(app)

    health_response = client.get("/api/health")
    capabilities_response = client.get("/api/capabilities")

    assert health_response.status_code == 200
    assert health_response.json()["status"] == "ok"
    assert health_response.json()["database"] == "ok"
    assert capabilities_response.status_code == 200
    capabilities = capabilities_response.json()
    assert capabilities["features"]["built_in_demo_project"] is True
    assert capabilities["features"]["static_analysis"] is True
    assert capabilities["features"]["pr_review_pack"] is True
    assert capabilities["features"]["pr_review_markdown_export"] is True
    assert capabilities["features"]["demo_readiness"] is True
    assert capabilities["features"]["demo_script"] is True
    assert capabilities["features"]["demo_script_markdown_export"] is True
    assert capabilities["features"]["improvement_suggestions"] is True
    assert capabilities["features"]["improvement_report_export"] is True
    assert capabilities["features"]["source_browser"] is True
    assert capabilities["features"]["source_browser_return_to_lesson"] is True
    assert capabilities["features"]["practice_task_source_links"] is True
    assert capabilities["features"]["lesson_report_practice_tasks"] is True
    assert capabilities["features"]["report_page_lesson_download"] is True
    assert capabilities["features"]["interview_markdown_export"] is True
    assert capabilities["features"]["interview_readiness"] is True
    assert capabilities["features"]["interview_question_records"] is True
    assert capabilities["features"]["project_dashboard"] is True
    assert capabilities["llm"]["configured"] is False
