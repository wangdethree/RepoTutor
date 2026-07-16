from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.curriculum_agent import CurriculumAgent
from app.agents.quiz_agent import QuizAgent
from app.agents.teaching_agent import TeachingAgent
from app.api import routes
from app.diagrams.architecture_builder import build_all_diagrams
from app.main import app
from app.repositories.sqlite_repository import SQLiteRepository
from app.services.analysis_service import AnalysisService
from app.services.practice_task_service import PracticeTaskService
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
        practice_progress={
            "total_tasks": 3,
            "completed_tasks": 1,
            "remaining_tasks": 2,
            "completion_rate": 33,
            "lessons": [
                {
                    "order_index": 1,
                    "lesson_title": plan["lessons"][0]["title"],
                    "completed_task_count": 1,
                    "task_count": 3,
                    "pending_tasks": ["调用链复述", "改动影响演练"],
                }
            ],
        },
        improvement_suggestions=_sample_improvement_suggestions(),
    )

    assert "# FastAPI Shop 学习报告" in markdown
    assert "## 项目事实摘要" in markdown
    assert "## 学习路线进度" in markdown
    assert "## 动手任务进度" in markdown
    assert "调用链复述" in markdown
    assert "## 项目改进建议" in markdown
    assert "补齐核心流程测试" in markdown
    assert "面试说法" in markdown
    assert "FastAPI 后端服务" in markdown


def test_report_service_builds_lesson_markdown(tmp_path: Path) -> None:
    repository, project_id = _prepared_repository(tmp_path)
    project = repository.get_project(project_id)
    analysis = repository.get_analysis(project_id)
    plan = repository.get_learning_plan(project_id)
    assert project is not None
    assert analysis is not None
    assert plan is not None

    lesson = TeachingAgent().generate(AnalysisService().analyze(project_id, Path(project["root_path"])), plan["lessons"][0])
    quiz = QuizAgent().generate(AnalysisService().analyze(project_id, Path(project["root_path"])), lesson)
    practice_tasks = PracticeTaskService().build(lesson, quiz)
    practice_tasks["tasks"][0]["completed"] = True
    practice_tasks["completed_task_count"] = 1
    practice_tasks["completion_rate"] = 33

    markdown = ReportService().build_lesson_report(
        project=project,
        lesson=lesson,
        analysis=analysis,
        quiz=quiz,
        quiz_results=[],
        practice_tasks=practice_tasks,
    )

    assert f"# {lesson['title']}" in markdown
    assert "## 核心代码位置" in markdown
    assert "## 调用关系" in markdown
    assert "## 动手任务" in markdown
    assert "源码定位走读" in markdown
    assert "状态：已完成" in markdown
    assert "## 测验题" in markdown


def test_learning_report_api_returns_markdown_download(tmp_path: Path, monkeypatch) -> None:
    repository, project_id = _prepared_repository(tmp_path)
    monkeypatch.setattr(routes, "repository", repository)
    client = TestClient(app)

    preview_response = client.get(f"/api/projects/{project_id}/reports/learning")
    download_response = client.get(f"/api/projects/{project_id}/reports/learning.md")

    assert preview_response.status_code == 200
    assert "学习报告" in preview_response.json()["markdown"]
    assert "## 项目改进建议" in preview_response.json()["markdown"]
    assert download_response.status_code == 200
    assert download_response.headers["content-type"].startswith("text/markdown")
    assert "learning-report.md" in download_response.headers["content-disposition"]
    assert "## 项目改进建议" in download_response.text


def test_lesson_report_api_returns_markdown_download(tmp_path: Path, monkeypatch) -> None:
    repository, project_id = _prepared_repository(tmp_path)
    monkeypatch.setattr(routes, "repository", repository)
    client = TestClient(app)
    plan = repository.get_learning_plan(project_id)
    assert plan is not None
    lesson_id = plan["lessons"][0]["id"]

    response = client.get(f"/api/lessons/{lesson_id}/report.md")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "lesson-report.md" in response.headers["content-disposition"]
    assert "## 测验题" in response.text
    assert "## 动手任务" in response.text


def test_report_service_adds_improvement_suggestions_to_interview_markdown() -> None:
    markdown = ReportService().build_interview_report(
        project={"name": "FastAPI Shop", "original_filename": "fastapi_shop.zip"},
        kit={
            "title": "FastAPI Shop 面试讲解包",
            "fact_checked": True,
            "elevator_pitch": "这是一个用于演示 FastAPI 分层结构的项目。",
            "architecture_story": ["从路由进入服务层。"],
            "technical_highlights": ["静态分析生成学习路线。"],
            "tradeoffs": ["V1 使用确定性规则保证离线演示。"],
            "risk_points": ["需要继续补齐真实项目测试。"],
            "questions": [],
            "core_references": [],
            "closing_summary": "可以围绕入口、服务和数据三层收尾。",
        },
        readiness=None,
        improvement_suggestions=_sample_improvement_suggestions(),
    )

    assert "## 项目改进讲述素材" in markdown
    assert "补齐核心流程测试" in markdown
    assert "面试说法" in markdown
    assert "面试中可把这些点讲成" in markdown


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


def _sample_improvement_suggestions() -> dict:
    return {
        "suggestion_count": 1,
        "priority_counts": {"HIGH": 1, "MEDIUM": 0, "LOW": 0},
        "highest_priority": "HIGH",
        "next_actions": ["为项目导入、静态分析、学习路线生成各补 1 条接口测试。"],
        "suggestions": [
            {
                "id": "testing_baseline",
                "category": "测试兜底",
                "priority": "HIGH",
                "title": "补齐核心流程测试",
                "reason": "当前核心演示链路还需要更明确的自动化测试证据。",
                "action_items": [
                    "为项目导入、静态分析、学习路线生成各补 1 条接口测试。",
                    "为核心 service 增加确定性单元测试。",
                ],
                "interview_talking_point": "我会把这个项目下一步的工程化重点放在测试兜底上。",
                "related_files": ["backend/app/api/routes.py"],
                "related_lessons": [
                    {"id": "lesson-1", "title": "入口与路由", "order_index": 1},
                ],
            }
        ],
    }
