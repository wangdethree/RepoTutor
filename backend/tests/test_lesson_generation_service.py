from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.agents.curriculum_agent import CurriculumAgent
from app.llm.client import LLMResponse
from app.services.analysis_service import AnalysisService
from app.services.lesson_generation_service import LessonGenerationService


@dataclass
class FakeLLMClient:
    api_key: str
    content: str

    async def complete_json(self, messages):
        return LLMResponse(content=self.content)


def _analysis_and_lesson():
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
    return analysis, plan["lessons"][0]


@pytest.mark.asyncio
async def test_lesson_generation_uses_deterministic_mode_without_api_key() -> None:
    analysis, lesson = _analysis_and_lesson()
    service = LessonGenerationService(llm_client_factory=lambda: FakeLLMClient(api_key="", content="{}"))

    payload = await service.generate(analysis, lesson)

    assert payload["generation_mode"] == "deterministic"
    assert payload["fact_checked"] is True


@pytest.mark.asyncio
async def test_lesson_generation_accepts_valid_llm_output() -> None:
    analysis, lesson = _analysis_and_lesson()
    deterministic = LessonGenerationService(llm_client_factory=lambda: FakeLLMClient(api_key="", content="{}"))
    base_payload = await deterministic.generate(analysis, lesson)
    base_payload["summary"] = "LLM 增强后的总结"
    service = LessonGenerationService(
        llm_client_factory=lambda: FakeLLMClient(api_key="sk-test", content=json.dumps(base_payload, ensure_ascii=False))
    )

    payload = await service.generate(analysis, lesson)

    assert payload["generation_mode"] == "llm"
    assert payload["summary"] == "LLM 增强后的总结"


@pytest.mark.asyncio
async def test_lesson_generation_falls_back_when_llm_hallucinates_reference() -> None:
    analysis, lesson = _analysis_and_lesson()
    bad_payload = {
        "id": lesson["id"],
        "title": lesson["title"],
        "objectives": ["测试"],
        "why": "测试",
        "core_code_locations": [{"file": "fake.py", "line": 1, "name": "fake", "kind": "source"}],
        "architecture_hint": "测试",
        "explanation": ["测试"],
        "design_reason": "测试",
        "pitfalls": ["测试"],
        "summary": "测试",
        "quiz_entry": "/quiz",
    }
    service = LessonGenerationService(
        llm_client_factory=lambda: FakeLLMClient(api_key="sk-test", content=json.dumps(bad_payload, ensure_ascii=False))
    )

    payload = await service.generate(analysis, lesson)

    assert payload["generation_mode"] == "deterministic_fallback"
    assert "不存在的文件" in payload["llm_error"]

