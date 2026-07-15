from __future__ import annotations

from pathlib import Path

from app.schemas.analysis import AnalysisResult, CodeFile


class SourceFileNotFoundError(ValueError):
    """请求的源码文件不在分析结果中。"""


class SourceFileAccessError(ValueError):
    """请求的源码文件越过了项目根目录边界。"""


class SourceBrowserService:
    """只允许读取静态分析已确认的源码文件。"""

    def list_files(self, analysis: AnalysisResult) -> list[dict]:
        return [
            {
                "path": file.path,
                "module_type": file.module_type,
                "line_count": file.line_count,
                "imported_by": file.imported_by,
                "importance_score": file.importance_score,
                "summary": file.summary,
            }
            for file in analysis.files
        ]

    def read_file(self, analysis: AnalysisResult, file_path: str) -> dict:
        code_file = self._known_file(analysis, file_path)
        root_path = Path(analysis.root_path).resolve()
        target = (root_path / file_path).resolve()
        if not self._is_inside_root(root_path, target):
            raise SourceFileAccessError("源码文件路径越过项目根目录")
        try:
            lines = target.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError as exc:
            raise SourceFileNotFoundError("源码文件不存在或不可读取") from exc
        return {
            "file": self._file_payload(code_file),
            "content": "\n".join(lines),
            "lines": [{"number": index, "text": line} for index, line in enumerate(lines, start=1)],
        }

    def _known_file(self, analysis: AnalysisResult, file_path: str) -> CodeFile:
        for file in analysis.files:
            if file.path == file_path:
                return file
        raise SourceFileNotFoundError("源码文件不在项目分析结果中")

    def _file_payload(self, file: CodeFile) -> dict:
        return {
            "path": file.path,
            "module_type": file.module_type,
            "line_count": file.line_count,
            "imported_by": file.imported_by,
            "importance_score": file.importance_score,
            "summary": file.summary,
        }

    def _is_inside_root(self, root_path: Path, target: Path) -> bool:
        try:
            target.relative_to(root_path)
        except ValueError:
            return False
        return True
