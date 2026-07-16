from __future__ import annotations

import zipfile
import shutil
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app
from app.repositories.sqlite_repository import SQLiteRepository
from app.services.github_import_service import GitHubImportService


def test_import_github_project_reuses_safe_zip_flow(tmp_path: Path, monkeypatch) -> None:
    test_repository = SQLiteRepository(f"sqlite:///{tmp_path / 'github-import.db'}")
    source_zip = tmp_path / "repo.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("owner-repo-sha/app/main.py", "from fastapi import FastAPI\napp = FastAPI()\n")

    class FakeGitHubImportService(GitHubImportService):
        def download_zip(self, github_url: str, target_zip: Path):
            repo_ref = self.parse_repository_url(github_url)
            target_zip.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_zip, target_zip)
            return repo_ref

    monkeypatch.setattr(routes, "repository", test_repository)
    monkeypatch.setattr(routes, "github_import_service", FakeGitHubImportService())
    monkeypatch.setattr(routes, "settings", SimpleNamespace(upload_dir=tmp_path / "uploads"))
    client = TestClient(app)

    response = client.post(
        "/api/projects/import-github",
        json={
            "github_url": "https://github.com/wangdethree/RepoTutor",
            "project_name": "RepoTutor Remote",
            "python_level": "熟练",
            "fastapi_level": "做过简单项目",
            "learning_goal": "准备项目面试",
            "daily_time": "1 小时",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    project = payload["project"]
    assert project["name"] == "RepoTutor Remote"
    assert project["original_filename"] == "wangdethree-RepoTutor.zip"
    assert Path(project["root_path"]).name == "owner-repo-sha"
    assert (Path(project["root_path"]) / "app" / "main.py").exists()
    assert payload["profile"]["learning_goal"] == "准备项目面试"
    assert payload["github"]["url"] == "https://github.com/wangdethree/RepoTutor"


def test_import_github_project_rejects_invalid_url(tmp_path: Path, monkeypatch) -> None:
    test_repository = SQLiteRepository(f"sqlite:///{tmp_path / 'github-import.db'}")
    monkeypatch.setattr(routes, "repository", test_repository)
    monkeypatch.setattr(routes, "github_import_service", GitHubImportService())
    monkeypatch.setattr(routes, "settings", SimpleNamespace(upload_dir=tmp_path / "uploads"))
    client = TestClient(app)

    response = client.post(
        "/api/projects/import-github",
        json={
            "github_url": "https://github.com/wangdethree/RepoTutor/tree/main",
            "project_name": "Bad URL",
        },
    )

    assert response.status_code == 400
    assert "不支持分支" in response.json()["detail"]
