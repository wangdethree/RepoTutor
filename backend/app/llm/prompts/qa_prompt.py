from __future__ import annotations

import json

from app.schemas.analysis import AnalysisResult


def build_qa_messages(
    analysis: AnalysisResult,
    question: str,
    deterministic_answer: dict,
    code_context: list[dict] | None = None,
) -> list[dict[str, str]]:
    """构造项目问答增强 Prompt，只允许模型基于已验证事实回答。"""

    allowed_files = [
        {
            "path": file.path,
            "module_type": file.module_type,
            "line_count": file.line_count,
            "importance_score": file.importance_score,
        }
        for file in analysis.files[:30]
    ]
    allowed_routes = [
        {
            "file_path": route.file_path,
            "line": route.line,
            "http_method": route.http_method,
            "path": route.path,
            "handler": route.handler,
        }
        for route in analysis.routes[:30]
    ]
    payload = {
        "project_summary": analysis.summary.__dict__,
        "question": question,
        "allowed_files": allowed_files,
        "allowed_routes": allowed_routes,
        "code_context": code_context or [],
        "deterministic_answer": deterministic_answer,
        "output_contract": {
            "required_fields": ["question", "answer", "facts", "inferences", "references"],
            "reference_rule": "references 中的 file 必须来自 allowed_files，line 必须在文件行数范围内。",
            "grounding_rule": "answer 必须优先复用 facts 和 code_context；不确定时明确说明推断边界。",
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "你是 RepoTutor 的项目问答 Agent。必须基于给定仓库事实回答，"
                "禁止创造不存在的文件、函数、路由或依赖。只输出 JSON 对象。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]
