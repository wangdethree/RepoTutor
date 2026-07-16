from __future__ import annotations

from pathlib import Path

from app.agents.curriculum_agent import CurriculumAgent
from app.services.analysis_service import AnalysisService
from app.services.diff_impact_service import DiffImpactService


def test_diff_impact_service_maps_changed_file_to_dependents_and_lessons() -> None:
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    analysis = AnalysisService().analyze("demo", repo_root)
    plan = CurriculumAgent().generate(
        analysis,
        {
            "python_level": "基础",
            "fastapi_level": "了解基础",
            "learning_goal": "学会修改现有项目",
            "daily_time": "1 小时",
        },
    )
    diff_text = """diff --git a/app/models/user.py b/app/models/user.py
--- a/app/models/user.py
+++ b/app/models/user.py
@@ -1,2 +1,3 @@
+email_verified = True
"""

    result = DiffImpactService().analyze(analysis, diff_text, plan=plan)

    assert result["summary"]["changed_file_count"] == 1
    assert result["changed_files"][0]["path"] == "app/models/user.py"
    assert result["changed_files"][0]["known"] is True
    assert any(file["path"] == "app/repositories/user_repository.py" for file in result["impacted_files"])
    assert result["related_lessons"]
    assert result["recommendations"]


def test_diff_impact_service_reports_unknown_changed_files() -> None:
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    analysis = AnalysisService().analyze("demo", repo_root)
    diff_text = """diff --git a/docs/readme.md b/docs/readme.md
--- a/docs/readme.md
+++ b/docs/readme.md
@@ -1 +1 @@
-old
+new
"""

    result = DiffImpactService().analyze(analysis, diff_text)

    assert result["summary"]["unknown_changed_file_count"] == 1
    assert result["changed_files"][0]["known"] is False
    assert "不在静态分析结果中" in result["recommendations"][0]
