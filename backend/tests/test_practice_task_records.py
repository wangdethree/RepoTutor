from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.curriculum_agent import CurriculumAgent
from app.agents.quiz_agent import QuizAgent
from app.agents.teaching_agent import TeachingAgent
from app.api import routes
from app.main import app
from app.repositories.sqlite_repository import SQLiteRepository
from app.services.analysis_service import AnalysisService
from app.services.practice_task_service import PracticeTaskService


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


def test_project_practice_progress_summarizes_task_records(tmp_path: Path, monkeypatch) -> None:
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'practice-progress.db'}")
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
    plan = CurriculumAgent().generate(analysis, profile)
    repository.save_learning_plan(project["id"], plan)
    monkeypatch.setattr(routes, "repository", repository)
    client = TestClient(app)

    initial_response = client.get(f"/api/projects/{project['id']}/practice-progress")
    first_lesson = plan["lessons"][0]
    lesson_payload = TeachingAgent().generate(analysis, first_lesson)
    quiz = QuizAgent().generate(analysis, lesson_payload)
    first_task = PracticeTaskService().build(lesson_payload, quiz)["tasks"][0]
    repository.upsert_practice_task_record(first_lesson["id"], first_task["id"], True)
    refreshed_response = client.get(f"/api/projects/{project['id']}/practice-progress")

    assert initial_response.status_code == 200
    assert initial_response.json()["completed_tasks"] == 0
    assert refreshed_response.status_code == 200
    payload = refreshed_response.json()
    assert payload["total_tasks"] >= 1
    assert payload["completed_tasks"] == 1
    lesson_progress = next(lesson for lesson in payload["lessons"] if lesson["lesson_id"] == first_lesson["id"])
    assert lesson_progress["completed_task_count"] == 1
    assert first_task["title"] not in lesson_progress["pending_tasks"]
