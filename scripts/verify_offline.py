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
from app.services.analysis_service import AnalysisService
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

    print("offline verification passed")
    print(f"routes={len(analysis.routes)} models={len(analysis.models)} diagrams={len(diagrams)} lessons={plan['total_lessons']}")


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
