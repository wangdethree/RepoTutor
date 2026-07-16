from __future__ import annotations

from pathlib import Path

from app.agents.curriculum_agent import CurriculumAgent
from app.repositories.sqlite_repository import SQLiteRepository
from app.services.analysis_service import AnalysisService
from app.services.profile_service import build_profile_from_payload


def test_repository_derives_learning_goals_from_legacy_goal(tmp_path: Path) -> None:
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'profile.db'}")
    project = repository.create_project(
        "FastAPI Shop",
        "fastapi_shop.zip",
        Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop",
        {
            "python_level": "基础",
            "fastapi_level": "了解基础",
            "learning_goal": "看懂项目结构",
            "daily_time": "1 小时",
        },
    )

    profile = repository.get_profile(project["id"])

    assert profile is not None
    assert profile["learning_goal"] == "看懂项目结构"
    assert profile["learning_goals"] == ["看懂项目结构"]


def test_profile_payload_accepts_multiple_learning_goals() -> None:
    profile = build_profile_from_payload(
        {
            "python_level": "熟练",
            "fastapi_level": "做过简单项目",
            "learning_goals": ["看懂项目结构", "准备项目面试", "学会修改现有项目"],
            "daily_time": "2 小时",
        }
    )

    assert profile["learning_goal"] == "看懂项目结构、准备项目面试、学会修改现有项目"
    assert profile["learning_goals"] == ["看懂项目结构", "准备项目面试", "学会修改现有项目"]


def test_curriculum_agent_adds_goal_specific_lessons() -> None:
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    analysis = AnalysisService().analyze("demo", repo_root)
    profile = {
        "python_level": "熟练",
        "fastapi_level": "做过简单项目",
        "learning_goal": "看懂项目结构、掌握 FastAPI 开发、准备项目面试、学会修改现有项目",
        "learning_goals": ["看懂项目结构", "掌握 FastAPI 开发", "准备项目面试", "学会修改现有项目"],
        "daily_time": "1 小时",
    }

    plan = CurriculumAgent().generate(analysis, profile)
    titles = [lesson["title"] for lesson in plan["lessons"]]

    assert plan["total_lessons"] == 10
    assert "FastAPI 开发规范与扩展点" in titles
    assert "动手修改路径与影响检查" in titles
    assert "项目面试讲解与架构取舍" in titles
