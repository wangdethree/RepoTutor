from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.curriculum_agent import CurriculumAgent
from app.agents.quiz_agent import QuizAgent
from app.api import routes
from app.main import app
from app.repositories.sqlite_repository import SQLiteRepository
from app.services.analysis_service import AnalysisService


def test_learning_progress_tracks_lesson_status(tmp_path: Path) -> None:
    repository, project_id, plan = _prepared_repository(tmp_path)
    first_lesson_id = plan["lessons"][0]["id"]

    initial = repository.get_learning_progress(project_id)
    completed_lesson = repository.update_lesson_status(first_lesson_id, "COMPLETED", score=95, mastery_level="MASTERED")
    progress = repository.get_learning_progress(project_id)
    refreshed_plan = repository.get_learning_plan(project_id)

    assert initial["completion_rate"] == 0
    assert completed_lesson is not None
    assert completed_lesson["status"] == "COMPLETED"
    assert progress["completed_lessons"] == 1
    assert progress["completion_rate"] > 0
    assert progress["next_lesson_id"] == plan["lessons"][1]["id"]
    assert refreshed_plan is not None
    assert refreshed_plan["status"] == "IN_PROGRESS"
    assert refreshed_plan["lessons"][0]["status"] == "COMPLETED"


def test_quiz_submission_updates_lesson_progress(tmp_path: Path, monkeypatch) -> None:
    repository, project_id, plan = _prepared_repository(tmp_path)
    lesson = plan["lessons"][0]
    analysis_payload = repository.get_analysis(project_id)
    assert analysis_payload is not None
    quiz = QuizAgent().generate(AnalysisService().analyze(project_id, Path(analysis_payload["root_path"])), lesson)
    repository.save_quiz(quiz)
    monkeypatch.setattr(routes, "repository", repository)
    client = TestClient(app)
    answers = {
        question["id"]: (
            "main.py app/main.py FastAPI include_router Router Service Repository Database "
            "AuthService AuthService.login UserRepository get_by_email model schema test"
        )
        for question in quiz["questions"]
    }

    response = client.post(f"/api/quizzes/{quiz['id']}/submit", json=answers)

    assert response.status_code == 200
    assert response.json()["score"] >= 80
    updated_lesson = repository.get_lesson(lesson["id"])
    progress = repository.get_learning_progress(project_id)
    assert updated_lesson is not None
    assert updated_lesson["status"] == "COMPLETED"
    assert progress["completed_lessons"] == 1


def test_quiz_results_are_listed_for_review(tmp_path: Path, monkeypatch) -> None:
    repository, project_id, plan = _prepared_repository(tmp_path)
    lesson = plan["lessons"][0]
    analysis_payload = repository.get_analysis(project_id)
    assert analysis_payload is not None
    quiz = QuizAgent().generate(AnalysisService().analyze(project_id, Path(analysis_payload["root_path"])), lesson)
    repository.save_quiz(quiz)
    monkeypatch.setattr(routes, "repository", repository)
    client = TestClient(app)
    answers = {question["id"]: "" for question in quiz["questions"]}

    submit_response = client.post(f"/api/quizzes/{quiz['id']}/submit", json=answers)
    project_response = client.get(f"/api/projects/{project_id}/quiz-results")
    lesson_response = client.get(f"/api/lessons/{lesson['id']}/quiz-results")

    assert submit_response.status_code == 200
    assert project_response.status_code == 200
    assert lesson_response.status_code == 200
    project_results = project_response.json()["quiz_results"]
    lesson_results = lesson_response.json()["quiz_results"]
    assert len(project_results) == 1
    assert len(lesson_results) == 1
    assert project_results[0]["lesson_title"] == lesson["title"]
    assert project_results[0]["missing_points"]


def test_lesson_status_api_rejects_invalid_status(tmp_path: Path, monkeypatch) -> None:
    repository, _, plan = _prepared_repository(tmp_path)
    monkeypatch.setattr(routes, "repository", repository)
    client = TestClient(app)

    response = client.post(f"/api/lessons/{plan['lessons'][0]['id']}/status", json={"status": "DONE"})

    assert response.status_code == 400


def _prepared_repository(tmp_path: Path) -> tuple[SQLiteRepository, str, dict]:
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'progress.db'}")
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
    return repository, project["id"], plan
