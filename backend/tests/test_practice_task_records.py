from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.curriculum_agent import CurriculumAgent
from app.api import routes
from app.main import app
from app.repositories.sqlite_repository import SQLiteRepository
from app.services.analysis_service import AnalysisService


def test_practice_task_records_can_be_updated(tmp_path: Path, monkeypatch) -> None:
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'practice-task-records.db'}")
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    profile = {
        "python_level": "基础",
        "fastapi_level": "了解基础",
        "learning_goal": "看懂项目结构",
        "daily_time": "1 小时",
    }
    project = repository.create_project("FastAPI Shop", "fastapi_shop.zip", repo_root, profile)
    analysis = AnalysisService().analyze(project["id"], repo_root)
    repository.save_analysis(project["id"], analysis.to_dict())
    repository.save_learning_plan(project["id"], CurriculumAgent().generate(analysis, profile))
    monkeypatch.setattr(routes, "repository", repository)
    client = TestClient(app)
    lesson_id = repository.get_learning_plan(project["id"])["lessons"][0]["id"]

    tasks_response = client.get(f"/api/lessons/{lesson_id}/practice-tasks")
    task_id = tasks_response.json()["tasks"][0]["id"]
    update_response = client.post(
        f"/api/lessons/{lesson_id}/practice-tasks/{task_id}/status",
        json={"completed": True},
    )

    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["completed_task_count"] == 1
    assert payload["completion_rate"] > 0
    assert next(task for task in payload["tasks"] if task["id"] == task_id)["completed"] is True
