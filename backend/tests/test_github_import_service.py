from __future__ import annotations

from pathlib import Path

import pytest

from app.services.github_import_service import GitHubImportError, GitHubImportService
from app.utils.safe_zip import MAX_ZIP_BYTES


def test_parse_repository_url_accepts_public_repo_root() -> None:
    service = GitHubImportService()

    repo = service.parse_repository_url("https://github.com/wangdethree/RepoTutor/")

    assert repo.owner == "wangdethree"
    assert repo.repo == "RepoTutor"
    assert repo.zipball_url == "https://api.github.com/repos/wangdethree/RepoTutor/zipball"


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/wangdethree/RepoTutor",
        "https://example.com/wangdethree/RepoTutor",
        "https://github.com/wangdethree/RepoTutor/tree/main",
        "https://github.com/wangdethree/RepoTutor?tab=readme",
        "https://github.com/wangdethree/RepoTutor.git",
    ],
)
def test_parse_repository_url_rejects_unsupported_forms(url: str) -> None:
    service = GitHubImportService()

    with pytest.raises(GitHubImportError):
        service.parse_repository_url(url)


def test_detect_repo_root_uses_single_github_archive_folder(tmp_path: Path) -> None:
    extract_dir = tmp_path / "repo"
    repo_root = extract_dir / "owner-repo-sha"
    repo_root.mkdir(parents=True)
    (repo_root / "main.py").write_text("from fastapi import FastAPI\n", encoding="utf-8")

    assert GitHubImportService().detect_repo_root(extract_dir) == repo_root


def test_download_zip_rejects_oversized_content_length(tmp_path: Path, monkeypatch) -> None:
    class FakeResponse:
        headers = {"Content-Length": str(MAX_ZIP_BYTES + 1)}

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    def fake_urlopen(request, timeout):
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(GitHubImportError, match="超过 20 MB"):
        GitHubImportService().download_zip("https://github.com/wangdethree/RepoTutor", tmp_path / "repo.zip")

    assert not (tmp_path / "repo.zip").exists()
