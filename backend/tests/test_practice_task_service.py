from __future__ import annotations

from pathlib import Path

from app.agents.curriculum_agent import CurriculumAgent
from app.agents.quiz_agent import QuizAgent
from app.agents.teaching_agent import TeachingAgent
from app.services.analysis_service import AnalysisService
from app.services.practice_task_service import PracticeTaskService


def test_practice_task_service_builds_concrete_lesson_tasks() -> None:
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    analysis = AnalysisService().analyze("demo", repo_root)
    plan = CurriculumAgent().generate(
        analysis,
        {
            "python_level": "基础",
            "fastapi_level": "了解基础",
            "learning_goal": "看懂项目结构",
            "daily_time": "1 小时",
        },
    )
    lesson = TeachingAgent().generate(analysis, plan["lessons"][0])
    quiz = QuizAgent().generate(analysis, lesson)

    payload = PracticeTaskService().build(lesson, quiz)

    assert payload["lesson_id"] == lesson["id"]
    assert payload["task_count"] >= 2
    task_types = {task["task_type"] for task in payload["tasks"]}
    assert {"source_walkthrough", "change_impact"} <= task_types
    assert all(task["steps"] and task["acceptance_checks"] for task in payload["tasks"])
    assert any(task["target_files"] for task in payload["tasks"])
