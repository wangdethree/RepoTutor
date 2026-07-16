from __future__ import annotations

import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.agents.assessment_agent import AssessmentAgent
from app.agents.curriculum_agent import CurriculumAgent
from app.agents.qa_agent import QAAgent
from app.agents.quiz_agent import QuizAgent
from app.agents.remediation_agent import RemediationAgent
from app.diagrams.architecture_builder import build_all_diagrams
from app.services.demo_readiness_service import DemoReadinessService
from app.services.demo_script_service import DemoScriptService
from app.services.analysis_service import AnalysisService
from app.services.contextual_qa_service import ContextualQAService
from app.services.diff_impact_service import DiffImpactService
from app.services.incremental_learning_service import IncrementalLearningService
from app.services.pr_review_service import PRReviewService
from app.services.project_dashboard_service import ProjectDashboardService
from app.services.project_improvement_service import ProjectImprovementService
from app.services.report_service import ReportService
from app.utils.safe_zip import ZipSafetyError, safe_extract_zip


def main() -> None:
    """离线验证核心闭环，不依赖 FastAPI、Streamlit 或 pytest。"""

    verify_safe_zip()
    analysis = AnalysisService().analyze("demo", ROOT / "demo_repositories" / "fastapi_shop")
    assert analysis.summary.project_type == "FastAPI 后端服务"
    assert "FastAPI" in analysis.summary.tech_stack
    assert len(analysis.routes) >= 5
    assert analysis.dependencies

    diagrams = build_all_diagrams(analysis)
    assert len(diagrams) >= 6
    assert any(diagram.id == "database-er" for diagram in diagrams)

    profile = {
        "python_level": "基础",
        "fastapi_level": "了解基础",
        "learning_goal": "看懂项目结构",
        "daily_time": "1 小时",
    }
    plan = CurriculumAgent().generate(analysis, profile)
    assert plan["total_lessons"] >= 7

    answer = QAAgent().answer(analysis, "登录流程经过哪些函数？")
    assert answer["references"]

    quiz = QuizAgent().generate(analysis, plan["lessons"][0])
    answers = {
        question["id"]: (
            "main.py app/main.py FastAPI include_router Router Service Repository Database "
            "login AuthService AuthService.login UserRepository get_by_email app/api/auth.py model schema test"
        )
        for question in quiz["questions"]
    }
    result = AssessmentAgent().evaluate(quiz, answers)
    assert result["score"] >= 80

    low_result = AssessmentAgent().evaluate(quiz, {question["id"]: "" for question in quiz["questions"]})
    remediation = RemediationAgent().generate(analysis, plan["lessons"][0], {"id": "offline-result", **low_result})
    assert remediation["fact_checked"] is True
    assert remediation["retry_quiz"]["questions"]

    verify_v1_showcase_services(analysis.to_dict(), plan, [diagram.__dict__ for diagram in diagrams], result)
    verify_v2_change_understanding_services(analysis, plan)

    print("offline verification passed")
    print(f"routes={len(analysis.routes)} models={len(analysis.models)} diagrams={len(diagrams)} lessons={plan['total_lessons']}")


def verify_v1_showcase_services(analysis_payload: dict, plan: dict, diagrams: list[dict], quiz_result: dict) -> None:
    project = {"id": "demo", "name": "FastAPI Shop", "original_filename": "fastapi_shop.zip"}
    progress = {
        "plan_id": plan["id"],
        "total_lessons": plan["total_lessons"],
        "completed_lessons": 2,
        "needs_review_lessons": 0,
        "completion_rate": 80,
        "next_action": "CONTINUE_NEXT_LESSON",
        "lessons": [
            {
                "id": lesson["id"],
                "title": lesson["title"],
                "order_index": lesson["order_index"],
                "status": "COMPLETED" if lesson["order_index"] <= 2 else "NOT_STARTED",
                "related_files": lesson.get("related_files", []),
            }
            for lesson in plan["lessons"]
        ],
    }
    practice_progress = {
        "completion_rate": 80,
        "total_tasks": 6,
        "completed_tasks": 5,
        "remaining_tasks": 1,
        "lessons": [],
    }
    quiz_results = [{"score": quiz_result["score"]}]
    interview_readiness = {"readiness_score": 82}

    demo_readiness = DemoReadinessService().build(
        project=project,
        analysis=analysis_payload,
        plan=plan,
        diagrams=diagrams,
        progress=progress,
        practice_progress=practice_progress,
        quiz_results=quiz_results,
        interview_readiness=interview_readiness,
    )
    assert demo_readiness["readiness_score"] >= 80

    improvements = ProjectImprovementService().build(
        project=project,
        analysis=analysis_payload,
        plan=plan,
        progress=progress,
        practice_progress=practice_progress,
        quiz_results=quiz_results,
    )
    assert "suggestions" in improvements

    dashboard = ProjectDashboardService().build(
        project=project,
        analysis=analysis_payload,
        plan=plan,
        progress=progress,
        practice_progress=practice_progress,
        interview_readiness=interview_readiness,
        demo_readiness=demo_readiness,
        improvement_suggestions=improvements,
    )
    assert dashboard["overall_score"] > 0
    assert len(dashboard["dimensions"]) == 6

    script = DemoScriptService().build(
        project=project,
        analysis=analysis_payload,
        plan=plan,
        progress=progress,
        demo_readiness=demo_readiness,
        improvement_suggestions=improvements,
    )
    markdown = ReportService().build_demo_script_report(project, script)
    assert "演示讲稿" in markdown
    assert "## 演示顺序" in markdown


def verify_v2_change_understanding_services(analysis, plan: dict) -> None:
    project = {"id": "demo", "name": "FastAPI Shop", "original_filename": "fastapi_shop.zip"}
    diff_text = """diff --git a/app/api/orders.py b/app/api/orders.py
--- a/app/api/orders.py
+++ b/app/api/orders.py
@@ -1,2 +1,3 @@
+include_coupon = True
"""
    impact = DiffImpactService().analyze(analysis, diff_text, plan=plan)
    assert impact["summary"]["changed_file_count"] == 1

    review = PRReviewService().build(project, diff_text, impact)
    assert review["test_plan"]
    assert review["interview_talking_points"]

    markdown = ReportService().build_pr_review_report(project, review)
    assert "PR 讲解包" in markdown
    assert "## 评审清单" in markdown

    incremental = IncrementalLearningService().build(project, impact, review)
    assert incremental["source_checkpoints"]
    assert incremental["practice_tasks"]
    incremental_markdown = ReportService().build_incremental_learning_report(project, incremental)
    assert "增量学习建议" in incremental_markdown
    assert "## 源码检查点" in incremental_markdown

    contextual_qa = ContextualQAService().answer(
        analysis=analysis,
        question="订单接口这次改动要重点看哪里？",
        file_path="app/api/orders.py",
        symbol_name="create_order",
        plan=plan,
        diff_impact=impact,
    )
    assert contextual_qa["references"]
    assert contextual_qa["diff_focus"]["changed_files"] == ["app/api/orders.py"]
    assert contextual_qa["source_checkpoints"]


def verify_safe_zip() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp = Path(temp_dir)
        bad_zip = temp / "bad.zip"
        with zipfile.ZipFile(bad_zip, "w") as archive:
            archive.writestr("../evil.py", "print('bad')")
        try:
            safe_extract_zip(bad_zip, temp / "bad")
        except ZipSafetyError:
            pass
        else:
            raise AssertionError("path traversal zip should be rejected")

        good_zip = temp / "good.zip"
        with zipfile.ZipFile(good_zip, "w") as archive:
            archive.writestr("app/main.py", "from fastapi import FastAPI\n")
            archive.writestr(".env", "SECRET=1")
        extracted = safe_extract_zip(good_zip, temp / "good")
        assert len(extracted) == 1
        assert extracted[0].name == "main.py"


if __name__ == "__main__":
    main()
