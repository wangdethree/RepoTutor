from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.agents.curriculum_agent import CurriculumAgent
from app.api import routes
from app.main import app
from app.repositories.sqlite_repository import SQLiteRepository
from app.services.analysis_service import AnalysisService


def test_incremental_learning_api_returns_recommendations(tmp_path: Path, monkeypatch) -> None:
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'incremental-learning.db'}")
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    profile = {
        "python_level": "基础",
        "fastapi_level": "了解基础",
        "learning_goal": "看懂项目结构",
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

    response = client.post(f"/api/projects/{project['id']}/incremental-learning", json={"diff": diff_text})
    markdown_response = client.post(f"/api/projects/{project['id']}/incremental-learning.md", json={"diff": diff_text})

    assert response.status_code == 200
    payload = response.json()
    assert payload["title"] == "FastAPI Shop 增量学习建议"
    assert payload["source_checkpoints"]
    assert payload["practice_tasks"]
    assert payload["questions_to_ask"]
    assert markdown_response.status_code == 200
    assert markdown_response.headers["content-type"].startswith("text/markdown")
    assert "## 源码检查点" in markdown_response.text
