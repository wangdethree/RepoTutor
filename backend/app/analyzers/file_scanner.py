from __future__ import annotations

from pathlib import Path

from app.schemas.analysis import CodeFile
from app.utils.safe_zip import is_sensitive_path


IGNORED_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
}

TEXT_EXTENSIONS = {
    ".py",
    ".md",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".ini",
    ".cfg",
}


class FileScanner:
    """扫描仓库文件，只收集安全的文本文件元信息。"""

    def scan(self, root: Path) -> list[CodeFile]:
        files: list[CodeFile] = []
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
                continue
            if is_sensitive_path(path.relative_to(root)):
                continue
            if path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            if self._looks_binary(path):
                continue

            relative_path = path.relative_to(root).as_posix()
            line_count = self._line_count(path)
            files.append(
                CodeFile(
                    path=relative_path,
                    module_type=self.classify_module(relative_path),
                    line_count=line_count,
                )
            )
        return files

    def classify_module(self, relative_path: str) -> str:
        path = relative_path.lower()
        parts = set(Path(path).parts)
        if path.endswith("main.py") or "app.py" in parts:
            return "entrypoint"
        if "api" in parts or "routers" in parts or "routes" in parts:
            return "api"
        if "services" in parts:
            return "service"
        if "repositories" in parts or "dao" in parts:
            return "repository"
        if "models" in parts:
            return "model"
        if "schemas" in parts:
            return "schema"
        if "core" in parts or "config" in path:
            return "core"
        if "tests" in parts or path.startswith("test_"):
            return "test"
        if "migrations" in parts or "alembic" in parts:
            return "migration"
        return "support"

    def _line_count(self, path: Path) -> int:
        try:
            return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
        except OSError:
            return 0

    def _looks_binary(self, path: Path) -> bool:
        try:
            chunk = path.read_bytes()[:1024]
        except OSError:
            return True
        return b"\x00" in chunk

