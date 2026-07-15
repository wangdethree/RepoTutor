from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.curriculum_agent import CurriculumAgent
from app.api import routes
from app.main import app
from app.repositories.sqlite_repository import SQLiteRepository
from app.services.analysis_service import AnalysisService


def test_low_score_generates_remediation_and_retry_quiz(tmp_path: Path, monkeypatch) -> None:
    repository, _, plan = _prepared_repository(tmp_path)
    lesson_id = plan["lessons"][0]["id"]
    monkeypatch.setattr(routes, "repository", repository)
    client = TestClient(app)

    quiz_response = client.post(f"/api/lessons/{lesson_id}/quiz")
    quiz = quiz_response.json()
    blank_answers = {question["id"]: "" for question in quiz["questions"]}
    first_result_response = client.post(f"/api/quizzes/{quiz['id']}/submit", json=blank_answers)
    first_result = first_result_response.json()

    remediation_response = client.post(f"/api/quiz-results/{first_result['id']}/remediation")
    remediation = remediation_response.json()
    retry_quiz = remediation["retry_quiz"]
    retry_answers = {
        question["id"]: (
            "app/main.py app/api/auth.py main FastAPI include_router route service repository schema test "
            "login AuthService AuthService.login UserRepository get_by_email"
        )
        for question in retry_quiz["questions"]
    }
    retry_result_response = client.post(f"/api/quizzes/{retry_quiz['id']}/submit", json=retry_answers)
    retry_result = retry_result_response.json()

    assert first_result_response.status_code == 200
    assert first_result["score"] < 60
    assert first_result["recommended_action"] == "REMEDIAL_LESSON"
    assert remediation_response.status_code == 200
    assert remediation["fact_checked"] is True
    assert remediation["trigger_score"] == first_result["score"]
    assert remediation["code_locations"]
    assert retry_quiz["id"].startswith("retry-")
    assert retry_result_response.status_code == 200
    assert retry_result["score"] >= 80
    assert repository.get_lesson(lesson_id)["status"] == "COMPLETED"


def test_remediation_rejects_non_low_score_result(tmp_path: Path, monkeypatch) -> None:
    repository, _, plan = _prepared_repository(tmp_path)
    lesson_id = plan["lessons"][0]["id"]
    monkeypatch.setattr(routes, "repository", repository)
    client = TestClient(app)

    quiz = client.post(f"/api/lessons/{lesson_id}/quiz").json()
    answers = {
        question["id"]: (
            "app/main.py app/api/auth.py main FastAPI include_router route service repository schema test "
            "login AuthService AuthService.login UserRepository get_by_email"
        )
        for question in quiz["questions"]
    }
    result = client.post(f"/api/quizzes/{quiz['id']}/submit", json=answers).json()

    response = client.post(f"/api/quiz-results/{result['id']}/remediation")

    assert result["score"] >= 60
    assert response.status_code == 400


def _prepared_repository(tmp_path: Path) -> tuple[SQLiteRepository, str, dict]:
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'remediation.db'}")
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
