from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.curriculum_agent import CurriculumAgent
from app.api import routes
from app.diagrams.architecture_builder import build_all_diagrams
from app.main import app
from app.repositories.sqlite_repository import SQLiteRepository
from app.services.analysis_service import AnalysisService
from app.services.report_service import ReportService


def test_report_service_builds_learning_markdown(tmp_path: Path) -> None:
    repository, project_id = _prepared_repository(tmp_path)
    project = repository.get_project(project_id)
    profile = repository.get_profile(project_id)
    analysis = repository.get_analysis(project_id)
    plan = repository.get_learning_plan(project_id)
    assert project is not None
    assert profile is not None
    assert analysis is not None
    assert plan is not None

    markdown = ReportService().build_learning_report(
        project=project,
        profile=profile,
        analysis=analysis,
        plan=plan,
        progress=repository.get_learning_progress(project_id),
        diagrams=repository.get_diagrams(project_id),
    )

    assert "# FastAPI Shop 学习报告" in markdown
    assert "## 项目事实摘要" in markdown
    assert "## 学习路线进度" in markdown
    assert "FastAPI 后端服务" in markdown


def test_learning_report_api_returns_markdown_download(tmp_path: Path, monkeypatch) -> None:
    repository, project_id = _prepared_repository(tmp_path)
    monkeypatch.setattr(routes, "repository", repository)
    client = TestClient(app)

    preview_response = client.get(f"/api/projects/{project_id}/reports/learning")
    download_response = client.get(f"/api/projects/{project_id}/reports/learning.md")

    assert preview_response.status_code == 200
    assert "学习报告" in preview_response.json()["markdown"]
    assert download_response.status_code == 200
    assert download_response.headers["content-type"].startswith("text/markdown")
    assert "learning-report.md" in download_response.headers["content-disposition"]


def _prepared_repository(tmp_path: Path) -> tuple[SQLiteRepository, str]:
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'report.db'}")
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
    repository.save_diagrams(project["id"], [diagram.__dict__ for diagram in build_all_diagrams(analysis)])
    plan = CurriculumAgent().generate(analysis, profile)
    repository.save_learning_plan(project["id"], plan)
    repository.update_lesson_status(plan["lessons"][0]["id"], "COMPLETED", score=90, mastery_level="MASTERED")
    return repository, project["id"]
