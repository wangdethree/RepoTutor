from __future__ import annotations

from app.llm.validators import LessonOutputValidator
from app.schemas.analysis import AnalysisResult
from app.services.call_chain_service import CallChainService


class TeachingAgent:
    """生成引用真实代码事实的单节课程。"""

    def generate(self, analysis: AnalysisResult, lesson: dict) -> dict:
        related_files = lesson.get("related_files") or analysis.summary.core_modules[:4]
        references = self._references_for_files(analysis, related_files)
        call_chains = self._call_chains_for_lesson(analysis, related_files)
        payload = {
            "id": lesson["id"],
            "title": lesson["title"],
            "objectives": lesson["objectives"],
            "why": self._why(lesson["title"]),
            "core_code_locations": references,
            "call_chains": call_chains,
            "architecture_hint": self._architecture_hint(analysis, lesson),
            "explanation": self._explanation(analysis, lesson, references),
            "design_reason": self._design_reason(lesson["title"]),
            "pitfalls": self._pitfalls(lesson["title"]),
            "summary": f"本节完成后，应能围绕 {', '.join(related_files[:3])} 讲清它们在项目中的位置。",
            "quiz_entry": f"/api/lessons/{lesson['id']}/quiz",
        }
        return LessonOutputValidator(analysis).validate(payload)

    def _call_chains_for_lesson(self, analysis: AnalysisResult, related_files: list[str]) -> list[dict]:
        chains = CallChainService().build_route_chains(analysis)
        matched = [
            chain
            for chain in chains
            if any(step["file"] in related_files for step in chain["steps"]) or chain["route"].get("file") in related_files
        ]
        return (matched or chains[:1])[:3]

    def _references_for_files(self, analysis: AnalysisResult, files: list[str]) -> list[dict]:
        references: list[dict] = []
        for file_path in files:
            file_symbols = [symbol for symbol in analysis.symbols if symbol.file_path == file_path][:5]
            file_routes = [route for route in analysis.routes if route.file_path == file_path][:5]
            if not file_symbols and not file_routes:
                references.append({"file": file_path, "line": 1, "name": "文件级阅读", "kind": "file"})
            for route in file_routes:
                references.append(
                    {
                        "file": route.file_path,
                        "line": route.line,
                        "name": f"{route.http_method} {route.path} -> {route.handler}",
                        "kind": "route",
                    }
                )
            for symbol in file_symbols:
                references.append(
                    {
                        "file": symbol.file_path,
                        "line": symbol.start_line,
                        "name": symbol.name,
                        "kind": symbol.symbol_type,
                    }
                )
        return references[:12]

    def _why(self, title: str) -> str:
        if "入口" in title:
            return "入口文件决定了应用如何被创建、配置和挂载路由，是理解整个项目的第一张地图。"
        if "路由" in title:
            return "路由连接外部 HTTP 请求和内部业务函数，先看路由能快速建立用户操作到代码位置的对应关系。"
        if "数据库" in title:
            return "数据库模型定义了核心业务对象和关系，是理解业务约束和修改影响范围的关键。"
        return "本节用于把分散的代码事实整理成可复述的项目理解。"

    def _architecture_hint(self, analysis: AnalysisResult, lesson: dict) -> str:
        modules = sorted({file.module_type for file in analysis.files if file.path in lesson.get("related_files", [])})
        return f"相关文件主要落在这些层：{', '.join(modules) or 'support'}。可配合系统分层架构图和文件依赖图阅读。"

    def _explanation(self, analysis: AnalysisResult, lesson: dict, references: list[dict]) -> list[str]:
        points = [
            f"项目类型识别为：{analysis.summary.project_type}。",
            f"本节建议先阅读 {', '.join(lesson.get('related_files', [])[:3])}。",
        ]
        if references:
            first = references[0]
            points.append(f"第一个锚点是 {first['file']}:{first['line']} 的 {first['name']}。")
        if analysis.routes:
            points.append(f"仓库中已识别 {len(analysis.routes)} 个 FastAPI 路由，可用路由列表反查处理函数。")
        if analysis.dependencies:
            points.append("文件依赖图中的边来自 import 语句，适合判断修改一个文件会影响哪些模块。")
        return points

    def _design_reason(self, title: str) -> str:
        if "Service" in title:
            return "Service 层把业务规则从路由函数中拆出，便于测试、复用和控制事务边界。"
        if "Schema" in title:
            return "Schema 层让请求校验和响应结构显式化，减少路由函数中的手写校验逻辑。"
        if "仓储" in title:
            return "Repository 层隔离数据库访问，降低业务逻辑对 ORM 细节的直接依赖。"
        return "分层阅读能把入口、业务、数据和横切模块拆开理解，降低陌生项目的认知负担。"

    def _pitfalls(self, title: str) -> list[str]:
        common = ["不要把推断关系当成 AST 已确认关系", "优先引用真实文件和行号回答问题"]
        if "路由" in title:
            common.append("注意 APIRouter 可能通过 include_router 在入口文件中统一挂载")
        if "数据库" in title:
            common.append("字段默认值、外键和 relationship 需要一起看，不能只看类名")
        return common
