from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from app.agents.teaching_agent import TeachingAgent
from app.llm.client import LLMClient
from app.llm.prompts.lesson_prompt import build_lesson_messages
from app.llm.validators import LessonOutputValidator
from app.schemas.analysis import AnalysisResult


class LessonGenerationService:
    """课程生成服务：确定性生成优先，LLM 增强可选且必须通过事实校验。"""

    def __init__(
        self,
        teaching_agent: TeachingAgent | None = None,
        llm_client_factory: Callable[[], LLMClient] | None = None,
    ) -> None:
        self.teaching_agent = teaching_agent or TeachingAgent()
        self.llm_client_factory = llm_client_factory or LLMClient

    async def generate(self, analysis: AnalysisResult, lesson: dict) -> dict:
        deterministic = self.teaching_agent.generate(analysis, lesson)
        deterministic["generation_mode"] = "deterministic"
        deterministic["llm_error"] = ""

        llm_client = self.llm_client_factory()
        if not llm_client.api_key:
            return deterministic

        try:
            messages = build_lesson_messages(analysis, lesson, deterministic)
            response = await llm_client.complete_json(messages)
            payload = json.loads(response.content)
            validated = LessonOutputValidator(analysis).validate(payload)
            validated["generation_mode"] = "llm"
            validated["llm_error"] = ""
            return validated
        except Exception as exc:
            fallback = dict(deterministic)
            fallback["generation_mode"] = "deterministic_fallback"
            fallback["llm_error"] = str(exc)
            return fallback

