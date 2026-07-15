from __future__ import annotations

from pathlib import Path

from app.llm.context import LessonCodeContextBuilder
from app.schemas.analysis import AnalysisResult, CodeFile, ProjectSummary


def test_lesson_code_context_reads_verified_file_ranges(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "app.py").write_text("from fastapi import FastAPI\n\napp = FastAPI()\n", encoding="utf-8")
    analysis = _analysis(repo_root, [CodeFile(path="app.py", module_type="entry", line_count=3)])
    lesson = {"related_files": ["app.py"]}
    deterministic = {
        "core_code_locations": [{"file": "app.py", "line": 3, "name": "app", "kind": "variable"}],
    }

    snippets = LessonCodeContextBuilder(max_snippets=2, context_radius=2).build(analysis, lesson, deterministic)

    assert snippets
    assert snippets[0]["file"] == "app.py"
    assert snippets[0]["start_line"] == 1
    assert "3: app = FastAPI()" in snippets[0]["code"]


def test_lesson_code_context_rejects_paths_outside_repository(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (tmp_path / "outside.py").write_text("secret = True\n", encoding="utf-8")
    analysis = _analysis(repo_root, [CodeFile(path="../outside.py", module_type="source", line_count=1)])
    lesson = {"related_files": ["../outside.py"]}
    deterministic = {
        "core_code_locations": [{"file": "../outside.py", "line": 1, "name": "outside", "kind": "file"}],
    }

    snippets = LessonCodeContextBuilder().build(analysis, lesson, deterministic)

    assert snippets == []


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
