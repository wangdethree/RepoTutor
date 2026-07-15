from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import routes
from app.main import app
from app.repositories.sqlite_repository import SQLiteRepository
from app.schemas.analysis import AnalysisResult, CodeFile, ProjectSummary
from app.services.analysis_service import AnalysisService
from app.services.source_browser_service import SourceBrowserService, SourceFileAccessError


def test_source_browser_reads_only_known_files(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n", encoding="utf-8")
    analysis = _analysis(repo_root, [CodeFile(path="main.py", module_type="entrypoint", line_count=2)])

    payload = SourceBrowserService().read_file(analysis, "main.py")

    assert payload["file"]["path"] == "main.py"
    assert payload["lines"][1]["number"] == 2
    assert "FastAPI" in payload["content"]


def test_source_browser_blocks_path_traversal_even_when_analysis_is_poisoned(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (tmp_path / "outside.py").write_text("secret = True\n", encoding="utf-8")
    analysis = _analysis(repo_root, [CodeFile(path="../outside.py", module_type="source", line_count=1)])

    with pytest.raises(SourceFileAccessError):
        SourceBrowserService().read_file(analysis, "../outside.py")


def test_source_browser_api_serves_analyzed_files(tmp_path: Path, monkeypatch) -> None:
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'source-api.db'}")
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    project = repository.create_project(
        name="FastAPI Shop",
        original_filename="fastapi_shop.zip",
        root_path=repo_root,
        profile={
            "python_level": "基础",
            "fastapi_level": "了解基础",
            "learning_goal": "看懂项目结构",
            "daily_time": "1 小时",
        },
    )
    analysis = AnalysisService().analyze(project["id"], repo_root)
    repository.save_analysis(project["id"], analysis.to_dict())
    monkeypatch.setattr(routes, "repository", repository)
    client = TestClient(app)

    files_response = client.get(f"/api/projects/{project['id']}/source-files")
    file_response = client.get(f"/api/projects/{project['id']}/source-files/app/main.py")

    assert files_response.status_code == 200
    assert any(file["path"] == "app/main.py" for file in files_response.json()["files"])
    assert file_response.status_code == 200
    assert "FastAPI" in file_response.json()["content"]


def _analysis(root_path: Path, files: list[CodeFile]) -> AnalysisResult:
    return AnalysisResult(
        project_id="demo",
        root_path=str(root_path),
        summary=ProjectSummary(
            project_type="FastAPI",
            tech_stack=["FastAPI"],
            file_count=len(files),
            python_file_count=len(files),
            line_count=sum(file.line_count for file in files),
            route_count=0,
            model_count=0,
            schema_count=0,
            difficulty="入门",
            estimated_days=1,
            core_modules=[file.path for file in files],
        ),
        files=files,
    )
