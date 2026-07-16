from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.curriculum_agent import CurriculumAgent
from app.api import routes
from app.main import app
from app.repositories.sqlite_repository import SQLiteRepository
from app.services.analysis_service import AnalysisService


def test_contextual_qa_api_returns_source_followup_payload(tmp_path: Path, monkeypatch) -> None:
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'contextual-qa.db'}")
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    profile = {
        "python_level": "基础",
        "fastapi_level": "了解基础",
        "learning_goal": "学会修改现有项目",
        "daily_time": "1 小时",
    }
    project = repository.create_project("FastAPI Shop", "fastapi_shop.zip", repo_root, profile)
    analysis = AnalysisService().analyze(project["id"], repo_root)
    repository.save_analysis(project["id"], analysis.to_dict())
    repository.save_learning_plan(project["id"], CurriculumAgent().generate(analysis, profile))
    monkeypatch.setattr(routes, "repository", repository)
    client = TestClient(app)
    diff_text = """diff --git a/app/api/orders.py b/app/api/orders.py
--- a/app/api/orders.py
+++ b/app/api/orders.py
@@ -1,2 +1,3 @@
+include_coupon = True
"""

    response = client.post(
        f"/api/projects/{project['id']}/contextual-qa",
        json={
            "question": "订单接口这次改动要重点看哪里？",
            "file_path": "app/api/orders.py",
            "symbol_name": "create_order",
            "diff": diff_text,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["fact_checked"] is True
    assert payload["scope"]["file_path"] == "app/api/orders.py"
    assert payload["scope"]["diff_attached"] is True
    assert payload["related_files"]
    assert payload["references"]
    assert payload["diff_focus"]["changed_files"] == ["app/api/orders.py"]
