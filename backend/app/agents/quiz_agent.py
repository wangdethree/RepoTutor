from __future__ import annotations

from app.schemas.analysis import AnalysisResult
from app.services.call_chain_service import CallChainService


class QuizAgent:
    """基于课程和项目事实生成 3 到 5 道测验。"""

    def generate(self, analysis: AnalysisResult, lesson: dict) -> dict:
        related_files = lesson.get("related_files") or analysis.summary.core_modules[:3]
        first_file = related_files[0] if related_files else (analysis.files[0].path if analysis.files else "main.py")
        first_route = analysis.routes[0] if analysis.routes else None
        call_chain = CallChainService().build_primary_chain(analysis)
        call_symbols = [step["symbol"] for step in call_chain.get("steps", [])]
        questions = [
            {
                "id": "q1",
                "type": "基础理解题",
                "prompt": f"本节最先应该定位哪个核心文件？请说明它的作用。",
                "expected_keywords": [first_file.split("/")[-1], first_file],
            },
            {
                "id": "q2",
                "type": "代码定位题",
                "prompt": "如果要确认项目入口或路由挂载关系，你会查看哪些文件或函数？",
                "expected_keywords": ["main", "router", "include_router", "FastAPI"],
            },
            {
                "id": "q3",
                "type": "调用链题",
                "prompt": self._call_chain_prompt(call_chain),
                "expected_keywords": call_symbols[:4] or ["Router", "Service", "Repository", "Database"],
            },
        ]
        if first_route:
            questions.append(
                {
                    "id": "q4",
                    "type": "代码定位题",
                    "prompt": f"{first_route.http_method} {first_route.path} 对应的处理函数是什么？",
                    "expected_keywords": [first_route.handler, first_route.file_path],
                }
            )
        questions.append(
            {
                "id": "q5",
                "type": "修改影响题",
                "prompt": "如果修改一个模型字段，哪些模块可能需要一起检查？",
                "expected_keywords": ["model", "schema", "repository", "service", "test"],
            }
        )
        return {
            "id": f"quiz-{lesson['id']}",
            "lesson_id": lesson["id"],
            "questions": questions[:5],
        }

    def _call_chain_prompt(self, call_chain: dict) -> str:
        route = call_chain.get("route") or {}
        if route:
            return (
                f"请描述 {route['method']} {route['path']} 从处理函数到后续核心函数/方法的主要调用路径，"
                "并说明每一步大致负责什么。"
            )
        return "请描述一次 HTTP 请求从 Router 到 Service/Repository 的主要路径。"
