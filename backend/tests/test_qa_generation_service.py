from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.llm.client import LLMResponse
from app.repositories.sqlite_repository import SQLiteRepository
from app.services.analysis_service import AnalysisService
from app.services.qa_generation_service import QAGenerationService


@dataclass
class FakeLLMClient:
    api_key: str
    content: str
    model: str = "fake-model"
    base_url: str = "https://fake.local/v1"

    async def complete_json(self, messages):
        return LLMResponse(content=self.content)


def _analysis():
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    return AnalysisService().analyze("demo", repo_root)


@pytest.mark.asyncio
async def test_qa_generation_uses_deterministic_mode_without_api_key() -> None:
    analysis = _analysis()
    service = QAGenerationService(llm_client_factory=lambda: FakeLLMClient(api_key="", content="{}"))

    payload = await service.answer(analysis, "登录流程经过哪些函数？")

    assert payload["generation_mode"] == "deterministic"
    assert payload["fact_checked"] is True
    assert payload["references"]


@pytest.mark.asyncio
async def test_qa_generation_accepts_valid_llm_answer() -> None:
    analysis = _analysis()
    deterministic = QAGenerationService(llm_client_factory=lambda: FakeLLMClient(api_key="", content="{}"))
    base_payload = await deterministic.answer(analysis, "登录流程经过哪些函数？")
    base_payload["answer"] = "LLM 增强后的登录流程说明"
    service = QAGenerationService(
        llm_client_factory=lambda: FakeLLMClient(api_key="sk-test", content=json.dumps(base_payload, ensure_ascii=False))
    )

    payload = await service.answer(analysis, "登录流程经过哪些函数？")

    assert payload["generation_mode"] == "llm"
    assert payload["answer"] == "LLM 增强后的登录流程说明"


@pytest.mark.asyncio
async def test_qa_generation_falls_back_and_records_validation_failure(tmp_path: Path) -> None:
    analysis = _analysis()
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'qa-audit.db'}")
    bad_payload = {
        "question": "登录流程经过哪些函数？",
        "answer": "测试",
        "facts": ["测试"],
        "inferences": ["测试"],
        "references": [{"file": "fake.py", "line": 1, "name": "fake", "kind": "source"}],
    }
    service = QAGenerationService(
        llm_client_factory=lambda: FakeLLMClient(api_key="sk-test", content=json.dumps(bad_payload, ensure_ascii=False)),
        repository=repository,
    )

    payload = await service.answer(analysis, "登录流程经过哪些函数？")

    logs = repository.list_llm_call_logs(analysis.project_id)
    detail = repository.get_llm_call_log(logs[0]["id"])
    assert payload["generation_mode"] == "deterministic_fallback"
    assert "不存在的文件" in payload["llm_error"]
    assert logs[0]["lesson_id"] == "project_qa"
    assert logs[0]["status"] == "FAILED_VALIDATION"
    assert detail is not None
    prompt_payload = json.loads(detail["prompt"][1]["content"])
    assert prompt_payload["code_context"]
