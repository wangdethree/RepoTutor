from __future__ import annotations

from pathlib import Path

from app.agents.assessment_agent import AssessmentAgent
from app.agents.curriculum_agent import CurriculumAgent
from app.agents.quiz_agent import QuizAgent
from app.services.analysis_service import AnalysisService


def test_curriculum_quiz_and_assessment_flow() -> None:
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    analysis = AnalysisService().analyze("demo", repo_root)
    profile = {
        "python_level": "基础",
        "fastapi_level": "了解基础",
        "learning_goal": "看懂项目结构",
        "daily_time": "1 小时",
    }

    plan = CurriculumAgent().generate(analysis, profile)
    quiz = QuizAgent().generate(analysis, plan["lessons"][0])
    answers = {
        question["id"]: (
            "app/main.py main.py FastAPI include_router Router Service Repository "
            "Database login app/api/auth.py model schema test"
        )
        for question in quiz["questions"]
    }
    result = AssessmentAgent().evaluate(quiz, answers)

    assert plan["total_lessons"] >= 7
    assert plan["lessons"][0]["project_id"] == "demo"
    assert len(quiz["questions"]) >= 3
    assert result["score"] >= 60
