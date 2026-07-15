from __future__ import annotations

from pathlib import Path

from app.schemas.analysis import AnalysisResult


class LessonCodeContextBuilder:
    """从已分析源码中提取短代码片段，作为 LLM 课程增强的事实上下文。"""

    def __init__(self, max_snippets: int = 6, context_radius: int = 8, max_total_chars: int = 12000) -> None:
        self.max_snippets = max_snippets
        self.context_radius = context_radius
        self.max_total_chars = max_total_chars

    def build(self, analysis: AnalysisResult, lesson: dict, deterministic_lesson: dict) -> list[dict]:
        known_files = {file.path: file for file in analysis.files}
        root_path = Path(analysis.root_path).resolve()
        snippets: list[dict] = []
        seen_ranges: set[tuple[str, int, int]] = set()
        used_chars = 0

        candidates = self._candidate_ranges(lesson, deterministic_lesson, known_files)
        for candidate in candidates:
            if len(snippets) >= self.max_snippets or used_chars >= self.max_total_chars:
                break
            file_path = candidate["file"]
            code_file = known_files.get(file_path)
            if not code_file:
                continue
            start_line = max(1, min(candidate["start_line"], code_file.line_count))
            end_line = max(start_line, min(candidate["end_line"], code_file.line_count))
            key = (file_path, start_line, end_line)
            if key in seen_ranges:
                continue

            code = self._read_snippet(root_path, file_path, start_line, end_line)
            if not code:
                continue
            remaining = self.max_total_chars - used_chars
            if remaining <= 0:
                break
            if len(code) > remaining:
                code = code[:remaining]

            snippets.append(
                {
                    "file": file_path,
                    "start_line": start_line,
                    "end_line": end_line,
                    "reason": candidate["reason"],
                    "code": code,
                }
            )
            seen_ranges.add(key)
            used_chars += len(code)
        return snippets

    def _candidate_ranges(self, lesson: dict, deterministic_lesson: dict, known_files: dict) -> list[dict]:
        candidates: list[dict] = []
        for location in deterministic_lesson.get("core_code_locations", []):
            file_path = location.get("file")
            if file_path not in known_files:
                continue
            line = int(location.get("line") or 1)
            candidates.append(
                {
                    "file": file_path,
                    "start_line": line - self.context_radius,
                    "end_line": line + self.context_radius,
                    "reason": f"{location.get('kind', 'code')}:{location.get('name', '核心位置')}",
                }
            )

        for file_path in lesson.get("related_files", []):
            if file_path not in known_files:
                continue
            candidates.append(
                {
                    "file": file_path,
                    "start_line": 1,
                    "end_line": self.context_radius * 2,
                    "reason": "lesson_related_file",
                }
            )
        return candidates

    def _read_snippet(self, root_path: Path, file_path: str, start_line: int, end_line: int) -> str:
        candidate = (root_path / file_path).resolve()
        if not self._is_inside_root(root_path, candidate):
            return ""
        try:
            lines = candidate.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return ""

        selected = lines[start_line - 1 : end_line]
        return "\n".join(f"{line_number}: {line}" for line_number, line in enumerate(selected, start=start_line))

    def _is_inside_root(self, root_path: Path, candidate: Path) -> bool:
        try:
            candidate.relative_to(root_path)
        except ValueError:
            return False
        return True
