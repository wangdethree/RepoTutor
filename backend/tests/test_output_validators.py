from __future__ import annotations

from pathlib import Path

import pytest

from app.agents.curriculum_agent import CurriculumAgent
from app.agents.teaching_agent import TeachingAgent
from app.llm.validators import LessonOutputValidator, OutputValidationError
from app.services.analysis_service import AnalysisService


def test_teaching_agent_returns_fact_checked_lesson() -> None:
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

    assert lesson["fact_checked"] is True
    assert lesson["core_code_locations"][0]["file"] in {file.path for file in analysis.files}


def test_lesson_validator_rejects_unknown_file_reference() -> None:
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    analysis = AnalysisService().analyze("demo", repo_root)
    payload = {
        "id": "lesson-1",
        "title": "测试课程",
        "objectives": ["定位入口"],
        "why": "测试",
        "core_code_locations": [{"file": "not_exists.py", "line": 1, "name": "fake", "kind": "source"}],
        "explanation": ["测试"],
        "design_reason": "测试",
        "pitfalls": ["测试"],
        "summary": "测试",
        "quiz_entry": "/quiz",
    }

    with pytest.raises(OutputValidationError):
        LessonOutputValidator(analysis).validate(payload)

