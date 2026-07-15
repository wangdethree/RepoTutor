from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from app.agents.qa_agent import QAAgent
from app.llm.client import LLMClient
from app.llm.context import LessonCodeContextBuilder
from app.llm.prompts.qa_prompt import build_qa_messages
from app.llm.validators import OutputValidationError, QAOutputValidator
from app.repositories.sqlite_repository import SQLiteRepository
from app.schemas.analysis import AnalysisResult


class QAGenerationService:
    """项目问答服务：确定性答案兜底，LLM 增强必须通过事实校验。"""

    def __init__(
        self,
        qa_agent: QAAgent | None = None,
        llm_client_factory: Callable[[], LLMClient] | None = None,
        repository: SQLiteRepository | None = None,
        context_builder: LessonCodeContextBuilder | None = None,
    ) -> None:
        self.qa_agent = qa_agent or QAAgent()
        self.llm_client_factory = llm_client_factory or LLMClient
        self.repository = repository
        self.context_builder = context_builder or LessonCodeContextBuilder(max_snippets=5, context_radius=6)

    async def answer(self, analysis: AnalysisResult, question: str) -> dict:
        deterministic = QAOutputValidator(analysis).validate(self.qa_agent.answer(analysis, question))
        deterministic["generation_mode"] = "deterministic"
        deterministic["llm_error"] = ""

        llm_client = self.llm_client_factory()
        if not llm_client.api_key:
            return deterministic

        code_context = self._build_code_context(analysis, deterministic)
        messages = build_qa_messages(analysis, question, deterministic, code_context)
        response = None
        started = time.perf_counter()
        try:
            response = await llm_client.complete_json(messages)
            payload = json.loads(response.content)
            validated = QAOutputValidator(analysis).validate(payload)
            validated["generation_mode"] = "llm"
            validated["llm_error"] = ""
            self._record_llm_call(analysis, llm_client, messages, response, "SUCCEEDED", "", started)
            return validated
        except (json.JSONDecodeError, OutputValidationError) as exc:
            self._record_llm_call(analysis, llm_client, messages, response, "FAILED_VALIDATION", str(exc), started)
            return self._fallback(deterministic, str(exc))
        except Exception as exc:
            self._record_llm_call(analysis, llm_client, messages, response, "FAILED", str(exc), started)
            return self._fallback(deterministic, str(exc))

    def _build_code_context(self, analysis: AnalysisResult, answer: dict) -> list[dict]:
        related_files = []
        for reference in answer.get("references", []):
            file_path = reference.get("file")
            if file_path and file_path not in related_files:
                related_files.append(file_path)
        pseudo_lesson = {"related_files": related_files}
        pseudo_answer = {"core_code_locations": answer.get("references", [])}
        return self.context_builder.build(analysis, pseudo_lesson, pseudo_answer)

    def _fallback(self, deterministic: dict, error: str) -> dict:
        fallback = dict(deterministic)
        fallback["generation_mode"] = "deterministic_fallback"
        fallback["llm_error"] = error
        return fallback

    def _record_llm_call(
        self,
        analysis: AnalysisResult,
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
                lesson_id="project_qa",
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
            # 审计失败不能影响问答主流程。
            return
