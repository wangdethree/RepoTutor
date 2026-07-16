from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app
from app.repositories.sqlite_repository import SQLiteRepository
from app.services.analysis_service import AnalysisService


def test_dependency_graph_api_returns_nodes_and_edges(tmp_path: Path, monkeypatch) -> None:
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'dependency-graph.db'}")
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    project = repository.create_project(
        "FastAPI Shop",
        "fastapi_shop.zip",
        repo_root,
        {
            "python_level": "基础",
            "fastapi_level": "了解基础",
            "learning_goal": "看懂项目结构",
            "daily_time": "1 小时",
        },
    )
    analysis = AnalysisService().analyze(project["id"], repo_root)
    repository.save_analysis(project["id"], analysis.to_dict())
    monkeypatch.setattr(routes, "repository", repository)
    client = TestClient(app)

    response = client.get(f"/api/projects/{project['id']}/dependency-graph")

    assert response.status_code == 200
    graph = response.json()
    assert graph["summary"]["node_count"] >= 1
    assert graph["summary"]["edge_count"] >= 1
    assert any(node["id"] == "app/main.py" for node in graph["nodes"])
    assert all({"source", "target", "evidence"} <= set(edge) for edge in graph["edges"])
