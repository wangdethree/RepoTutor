from __future__ import annotations

from pathlib import Path

from app.agents.curriculum_agent import CurriculumAgent
from app.services.analysis_service import AnalysisService
from app.services.contextual_qa_service import ContextualQAService
from app.services.diff_impact_service import DiffImpactService


def _analysis():
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    return AnalysisService().analyze("demo", repo_root)


def test_contextual_qa_scopes_file_symbol_and_diff() -> None:
    analysis = _analysis()
    profile = {
        "python_level": "基础",
        "fastapi_level": "了解基础",
        "learning_goal": "学会修改现有项目",
        "daily_time": "1 小时",
    }
    plan = CurriculumAgent().generate(analysis, profile)
    diff_text = """diff --git a/app/api/orders.py b/app/api/orders.py
--- a/app/api/orders.py
+++ b/app/api/orders.py
@@ -1,2 +1,3 @@
+include_coupon = True
"""
    impact = DiffImpactService().analyze(analysis, diff_text, plan=plan)

    payload = ContextualQAService().answer(
        analysis=analysis,
        question="订单创建逻辑修改后会影响哪些 API 入口？",
        file_path="app/api/orders.py",
        symbol_name="create_order",
        plan=plan,
        diff_impact=impact,
    )

    assert payload["fact_checked"] is True
    assert payload["generation_mode"] == "deterministic"
    assert payload["scope"]["diff_attached"] is True
    assert payload["diff_focus"]["changed_files"] == ["app/api/orders.py"]
    assert any(file["path"] == "app/api/orders.py" for file in payload["related_files"])
    assert any(route["handler"] == "create_order" for route in payload["related_routes"])
    assert any(reference["file"] == "app/api/orders.py" for reference in payload["references"])
    assert payload["source_checkpoints"]
    assert payload["follow_up_questions"]


def test_contextual_qa_falls_back_to_core_modules_without_scope() -> None:
    analysis = _analysis()

    payload = ContextualQAService().answer(
        analysis=analysis,
        question="这个项目最核心的阅读入口是什么？",
    )

    assert payload["related_files"]
    assert payload["references"]
    assert payload["diff_focus"] is None
    assert "未提供 diff" in payload["answer"]
