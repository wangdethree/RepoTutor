from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.curriculum_agent import CurriculumAgent
from app.agents.interview_agent import InterviewAgent
from app.api import routes
from app.main import app
from app.repositories.sqlite_repository import SQLiteRepository
from app.services.analysis_service import AnalysisService
from app.services.report_service import ReportService


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


def test_interview_report_exports_markdown() -> None:
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    analysis = AnalysisService().analyze("demo", repo_root)
    kit = InterviewAgent().generate(analysis, {"learning_goal": "准备项目面试"})
    project = {
        "name": "FastAPI Shop",
        "original_filename": "fastapi_shop.zip",
    }
    readiness = {
        "readiness_score": 82,
        "readiness_level": "READY",
        "score_breakdown": {
            "course_completion": 90,
            "practice_completion": 80,
            "quiz_average": 85,
            "source_evidence": 100,
        },
        "checklist": [
            {
                "title": "课程路线完成度",
                "status": "DONE",
                "detail": "当前课程完成率 90%。",
                "action": "保持当前节奏。",
            }
        ],
        "recommended_actions": ["导出面试材料并进行口头演练。"],
        "weak_lessons": [],
        "pending_practice_lessons": [],
    }

    markdown = ReportService().build_interview_report(project, kit, readiness=readiness)

    assert "# FastAPI Shop 面试准备材料" in markdown
    assert "## 面试准备度" in markdown
    assert "准备度：82%" in markdown
    assert "## 高频问答" in markdown
    assert "## 核心源码证据" in markdown
    assert kit["questions"][0]["question"] in markdown


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
    assert payload["questions"][0]["mastered"] is False
    assert payload["question_mastery_rate"] == 0


def test_interview_kit_api_returns_markdown_download(tmp_path: Path, monkeypatch) -> None:
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'interview-report.db'}")
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

    response = client.get(f"/api/projects/{project['id']}/interview-kit.md")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "interview-kit.md" in response.headers["content-disposition"]
    assert "## 面试准备度" in response.text
    assert "## 项目改进讲述素材" in response.text
    assert "## 高频问答" in response.text


def test_interview_readiness_api_returns_checklist(tmp_path: Path, monkeypatch) -> None:
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'interview-readiness.db'}")
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
    repository.save_learning_plan(project["id"], CurriculumAgent().generate(analysis, profile))
    monkeypatch.setattr(routes, "repository", repository)
    client = TestClient(app)

    response = client.get(f"/api/projects/{project['id']}/interview-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert "readiness_score" in payload
    assert payload["readiness_level"] in {"READY", "ALMOST_READY", "NEEDS_WORK"}
    assert payload["checklist"]


def test_interview_question_status_can_be_updated(tmp_path: Path, monkeypatch) -> None:
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'interview-question-records.db'}")
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
    repository.save_learning_plan(project["id"], CurriculumAgent().generate(analysis, profile))
    monkeypatch.setattr(routes, "repository", repository)
    client = TestClient(app)
    kit_response = client.get(f"/api/projects/{project['id']}/interview-kit")
    question_id = kit_response.json()["questions"][0]["id"]

    update_response = client.post(
        f"/api/projects/{project['id']}/interview-questions/{question_id}/status",
        json={"mastered": True},
    )

    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["mastered_question_count"] == 1
    assert payload["question_mastery_rate"] > 0
    assert next(question for question in payload["questions"] if question["id"] == question_id)["mastered"] is True
