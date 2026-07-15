from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.curriculum_agent import CurriculumAgent
from app.agents.interview_agent import InterviewAgent
from app.api import routes
from app.main import app
from app.repositories.sqlite_repository import SQLiteRepository
from app.services.analysis_service import AnalysisService


def test_interview_agent_generates_fact_checked_kit() -> None:
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    analysis = AnalysisService().analyze("demo", repo_root)
    profile = {
        "python_level": "基础",
        "fastapi_level": "了解基础",
        "learning_goal": "准备项目面试",
        "daily_time": "1 小时",
    }

    kit = InterviewAgent().generate(analysis, profile)

    assert kit["fact_checked"] is True
    assert kit["title"].endswith("面试讲解包")
    assert "准备项目面试" in kit["elevator_pitch"]
    assert len(kit["questions"]) >= 4
    assert kit["core_references"]
    valid_files = {file.path: file.line_count for file in analysis.files}
    for reference in kit["core_references"]:
        assert reference["file"] in valid_files
        assert 1 <= reference["line"] <= valid_files[reference["file"]]


def test_interview_kit_api_returns_project_material(tmp_path: Path, monkeypatch) -> None:
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'interview.db'}")
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    profile = {
        "python_level": "基础",
        "fastapi_level": "了解基础",
        "learning_goal": "准备项目面试",
        "daily_time": "1 小时",
    }
    project = repository.create_project("FastAPI Shop", "fastapi_shop.zip", repo_root, profile)
    analysis = AnalysisService().analyze(project["id"], repo_root)
    repository.save_analysis(project["id"], analysis.to_dict())
    plan = CurriculumAgent().generate(analysis, profile)
    repository.save_learning_plan(project["id"], plan)
    monkeypatch.setattr(routes, "repository", repository)
    client = TestClient(app)

    response = client.get(f"/api/projects/{project['id']}/interview-kit")

    assert response.status_code == 200
    payload = response.json()
    assert payload["project_id"] == project["id"]
    assert payload["fact_checked"] is True
    assert payload["questions"][0]["references"]
