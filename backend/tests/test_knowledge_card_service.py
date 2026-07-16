from __future__ import annotations

from pathlib import Path

from app.agents.curriculum_agent import CurriculumAgent
from app.agents.quiz_agent import QuizAgent
from app.agents.teaching_agent import TeachingAgent
from app.services.analysis_service import AnalysisService
from app.services.knowledge_card_service import KnowledgeCardService


def test_knowledge_card_service_builds_cards_from_lesson_and_quiz() -> None:
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

    payload = KnowledgeCardService().build(lesson, quiz)

    assert payload["lesson_id"] == lesson["id"]
    assert payload["card_count"] >= 8
    categories = {card["category"] for card in payload["cards"]}
    assert {"学习目标", "源码定位", "易错点", "测验关键词"} <= categories
    assert any(card["references"] for card in payload["cards"])
