from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app
from app.repositories.sqlite_repository import SQLiteRepository


def test_bootstrap_fastapi_shop_demo_prepares_project(tmp_path: Path, monkeypatch) -> None:
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'demo-project.db'}")
    monkeypatch.setattr(routes, "repository", repository)
    client = TestClient(app)

    response = client.post("/api/demo-projects/fastapi-shop", json={})

    assert response.status_code == 200
    payload = response.json()
    project = payload["project"]
    assert project["name"] == "FastAPI Shop Demo"
    assert project["analysis_status"] == "ANALYZED"
    assert payload["demo"]["analysis_ready"] is True
    assert payload["demo"]["diagrams"] >= 3
    assert payload["demo"]["lessons"] >= 5
    assert repository.get_analysis(project["id"]) is not None
    assert repository.get_learning_plan(project["id"]) is not None


def test_bootstrap_fastapi_shop_demo_reuses_existing_project(tmp_path: Path, monkeypatch) -> None:
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'demo-project.db'}")
    monkeypatch.setattr(routes, "repository", repository)
    client = TestClient(app)

    first = client.post("/api/demo-projects/fastapi-shop", json={}).json()
    second = client.post("/api/demo-projects/fastapi-shop", json={}).json()

    assert second["project"]["id"] == first["project"]["id"]
    assert second["demo"]["created"] is False
