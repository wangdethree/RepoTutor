from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.schemas.analysis import AnalysisResult


class OutputValidationError(ValueError):
    """LLM 或 Agent 输出没有通过项目事实校验。"""


class CodeReferenceValidator:
    """校验输出中的文件与行号是否来自当前仓库事实库。"""

    def __init__(self, analysis: AnalysisResult) -> None:
        self.file_index = {file.path: file for file in analysis.files}

    def validate_many(self, references: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self.validate(reference) for reference in references]

    def validate(self, reference: dict[str, Any]) -> dict[str, Any]:
        file_path = str(reference.get("file", "")).strip()
        if not file_path:
            raise OutputValidationError("代码引用缺少 file 字段")
        if file_path not in self.file_index:
            raise OutputValidationError(f"代码引用指向不存在的文件: {file_path}")

        try:
            line = int(reference.get("line", 1))
        except (TypeError, ValueError) as exc:
            raise OutputValidationError(f"代码引用行号不是整数: {file_path}") from exc

        file_info = self.file_index[file_path]
        if line < 1 or line > max(file_info.line_count, 1):
            raise OutputValidationError(f"代码引用行号越界: {file_path}:{line}")

        normalized = dict(reference)
        normalized["file"] = file_path
        normalized["line"] = line
        normalized["name"] = str(reference.get("name") or "代码位置")
        normalized["kind"] = str(reference.get("kind") or "source")
        return normalized


class LessonOutputValidator:
    """校验课程输出结构，并确保所有代码引用可追溯。"""

    REQUIRED_STRING_FIELDS = ["id", "title", "why", "design_reason", "summary", "quiz_entry"]
    REQUIRED_LIST_FIELDS = ["objectives", "core_code_locations", "explanation", "pitfalls"]

    def __init__(self, analysis: AnalysisResult) -> None:
        self.reference_validator = CodeReferenceValidator(analysis)

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        lesson = deepcopy(payload)
        for field in self.REQUIRED_STRING_FIELDS:
            if not str(lesson.get(field, "")).strip():
                raise OutputValidationError(f"课程输出缺少字段: {field}")
        for field in self.REQUIRED_LIST_FIELDS:
            if not isinstance(lesson.get(field), list) or not lesson[field]:
                raise OutputValidationError(f"课程输出列表字段为空: {field}")

        lesson["objectives"] = [str(item) for item in lesson["objectives"]]
        lesson["explanation"] = [str(item) for item in lesson["explanation"]]
        lesson["pitfalls"] = [str(item) for item in lesson["pitfalls"]]
        lesson["core_code_locations"] = self.reference_validator.validate_many(lesson["core_code_locations"])
        lesson["fact_checked"] = True
        return lesson


class QAOutputValidator:
    """校验项目问答输出，确保回答引用仍然落在真实源码上。"""

    REQUIRED_STRING_FIELDS = ["question", "answer"]
    REQUIRED_LIST_FIELDS = ["facts", "inferences", "references"]

    def __init__(self, analysis: AnalysisResult) -> None:
        self.reference_validator = CodeReferenceValidator(analysis)

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        answer = deepcopy(payload)
        for field in self.REQUIRED_STRING_FIELDS:
            if not str(answer.get(field, "")).strip():
                raise OutputValidationError(f"问答输出缺少字段: {field}")
        for field in self.REQUIRED_LIST_FIELDS:
            if not isinstance(answer.get(field), list):
                raise OutputValidationError(f"问答输出字段不是列表: {field}")

        answer["facts"] = [str(item) for item in answer["facts"] if str(item).strip()]
        answer["inferences"] = [str(item) for item in answer["inferences"] if str(item).strip()]
        if not answer["facts"]:
            raise OutputValidationError("问答输出缺少事实依据")
        answer["references"] = self.reference_validator.validate_many(answer["references"])
        if not answer["references"]:
            raise OutputValidationError("问答输出缺少代码引用")
        answer["fact_checked"] = True
        return answer
