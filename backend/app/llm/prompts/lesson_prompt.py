from __future__ import annotations

import json

from app.schemas.analysis import AnalysisResult


def build_lesson_messages(analysis: AnalysisResult, lesson: dict, deterministic_lesson: dict) -> list[dict[str, str]]:
    """构造课程增强 Prompt，只暴露已验证的项目事实和确定性课程草稿。"""

    allowed_files = [
        {
            "path": file.path,
            "module_type": file.module_type,
            "line_count": file.line_count,
            "importance_score": file.importance_score,
        }
        for file in analysis.files[:20]
    ]
    allowed_routes = [
        {
            "file_path": route.file_path,
            "line": route.line,
            "http_method": route.http_method,
            "path": route.path,
            "handler": route.handler,
        }
        for route in analysis.routes[:20]
    ]
    payload = {
        "project_summary": analysis.summary.__dict__,
        "lesson": lesson,
        "allowed_files": allowed_files,
        "allowed_routes": allowed_routes,
        "deterministic_lesson": deterministic_lesson,
        "output_contract": {
            "required_fields": [
                "id",
                "title",
                "objectives",
                "why",
                "core_code_locations",
                "architecture_hint",
                "explanation",
                "design_reason",
                "pitfalls",
                "summary",
                "quiz_entry",
            ],
            "reference_rule": "core_code_locations 中的 file 必须来自 allowed_files，line 必须在文件行数范围内。",
        },
    }
    return [
        {
            "role": "system",
            "content": (
                "你是 RepoTutor 的课程生成 Agent。必须基于给定仓库事实生成课程，"
                "禁止创造不存在的文件、函数、路由或依赖。只输出 JSON 对象。"
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]

