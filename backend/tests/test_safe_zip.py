from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from app.utils.safe_zip import ZipSafetyError, safe_extract_zip


def test_safe_extract_rejects_path_traversal(tmp_path: Path) -> None:
    zip_path = tmp_path / "bad.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("../evil.py", "print('bad')")

    with pytest.raises(ZipSafetyError):
        safe_extract_zip(zip_path, tmp_path / "out")


def test_safe_extract_skips_sensitive_files(tmp_path: Path) -> None:
    zip_path = tmp_path / "demo.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("app/main.py", "from fastapi import FastAPI\n")
        archive.writestr(".env", "SECRET=1")
        archive.writestr("private.pem", "secret")

    extracted = safe_extract_zip(zip_path, tmp_path / "out")

    assert [path.name for path in extracted] == ["main.py"]
    assert not (tmp_path / "out" / ".env").exists()
    assert not (tmp_path / "out" / "private.pem").exists()

