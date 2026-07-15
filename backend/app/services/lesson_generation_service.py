from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from app.agents.teaching_agent import TeachingAgent
from app.llm.client import LLMClient
from app.llm.prompts.lesson_prompt import build_lesson_messages
from app.llm.validators import LessonOutputValidator, OutputValidationError
from app.repositories.sqlite_repository import SQLiteRepository
from app.schemas.analysis import AnalysisResult


class LessonGenerationService:
    """课程生成服务：确定性生成优先，LLM 增强可选且必须通过事实校验。"""

    def __init__(
        self,
        teaching_agent: TeachingAgent | None = None,
        llm_client_factory: Callable[[], LLMClient] | None = None,
        repository: SQLiteRepository | None = None,
    ) -> None:
        self.teaching_agent = teaching_agent or TeachingAgent()
        self.llm_client_factory = llm_client_factory or LLMClient
        self.repository = repository

    async def generate(self, analysis: AnalysisResult, lesson: dict) -> dict:
        deterministic = self.teaching_agent.generate(analysis, lesson)
        deterministic["generation_mode"] = "deterministic"
        deterministic["llm_error"] = ""

        llm_client = self.llm_client_factory()
        if not llm_client.api_key:
            return deterministic

        messages = build_lesson_messages(analysis, lesson, deterministic)
        response = None
        started = time.perf_counter()
        try:
            response = await llm_client.complete_json(messages)
            payload = json.loads(response.content)
            validated = LessonOutputValidator(analysis).validate(payload)
            validated["generation_mode"] = "llm"
            validated["llm_error"] = ""
            self._record_llm_call(analysis, lesson, llm_client, messages, response, "SUCCEEDED", "", started)
            return validated
        except (json.JSONDecodeError, OutputValidationError) as exc:
            self._record_llm_call(
                analysis,
                lesson,
                llm_client,
                messages,
                response,
                "FAILED_VALIDATION",
                str(exc),
                started,
            )
            fallback = dict(deterministic)
            fallback["generation_mode"] = "deterministic_fallback"
            fallback["llm_error"] = str(exc)
            return fallback
        except Exception as exc:
            self._record_llm_call(analysis, lesson, llm_client, messages, response, "FAILED", str(exc), started)
            fallback = dict(deterministic)
            fallback["generation_mode"] = "deterministic_fallback"
            fallback["llm_error"] = str(exc)
            return fallback

    def _record_llm_call(
        self,
        analysis: AnalysisResult,
        lesson: dict,
        llm_client: LLMClient,
        messages: list[dict[str, str]],
        response: Any,
        status: str,
        error: str,
        started: float,
    ) -> None:
        if not self.repository:
            return
        response_payload = {}
        if response:
            response_payload = {"content": response.content, "raw": response.raw}
        latency_ms = int((time.perf_counter() - started) * 1000)
        try:
            self.repository.record_llm_call(
                project_id=analysis.project_id,
                lesson_id=str(lesson.get("id", "")),
                provider="openai_compatible",
                model=llm_client.model,
                base_url=llm_client.base_url,
                prompt=messages,
                response=response_payload,
                status=status,
                error=error,
                latency_ms=latency_ms,
            )
        except Exception:
            # 审计失败不能影响课程生成主流程。
            return
