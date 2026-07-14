from __future__ import annotations

from pathlib import Path

from app.schemas.analysis import AnalysisResult


class QAAgent:
    """项目问答 Agent，只基于静态分析事实和真实源码片段回答。"""

    def answer(self, analysis: AnalysisResult, question: str) -> dict:
        normalized = question.lower()
        if self._contains(normalized, ["入口", "启动", "main", "app"]):
            return self._entrypoint_answer(analysis, question)
        if self._contains(normalized, ["jwt", "token", "过期", "expire"]):
            return self._keyword_answer(analysis, question, ["jwt", "token", "expire", "过期"])
        if self._contains(normalized, ["depends", "依赖注入", "dependency"]):
            return self._keyword_answer(analysis, question, ["Depends", "dependencies", "get_current_user"])
        if self._contains(normalized, ["修改", "影响", "字段", "模型"]):
            return self._impact_answer(analysis, question)
        if self._contains(normalized, ["登录", "login"]):
            return self._login_answer(analysis, question)
        return self._general_answer(analysis, question)

    def _entrypoint_answer(self, analysis: AnalysisResult, question: str) -> dict:
        entry_files = [file for file in analysis.files if file.module_type == "entrypoint"]
        references = self._references_from_files(analysis, [file.path for file in entry_files[:5]])
        if not entry_files:
            references = self._references_from_files(analysis, analysis.summary.core_modules[:3])
        facts = [
            f"项目类型识别为 {analysis.summary.project_type}",
            f"核心入口候选文件：{', '.join(item['file'] for item in references[:3])}",
        ]
        return self._response(question, facts, ["入口文件依据文件名和 FastAPI() 调用共同判断"], references)

    def _login_answer(self, analysis: AnalysisResult, question: str) -> dict:
        routes = [
            route
            for route in analysis.routes
            if "login" in route.path.lower() or "login" in route.handler.lower()
        ]
        route_files = [route.file_path for route in routes]
        service_files = [file.path for file in analysis.files if "auth" in file.path.lower() or "login" in file.path.lower()]
        references = self._references_from_files(analysis, sorted(set(route_files + service_files)))
        facts = [f"识别到登录相关路由 {route.http_method} {route.path} -> {route.handler}" for route in routes]
        if not facts:
            facts.append("未在 FastAPI 路由中识别到明确的 login 处理函数")
        return self._response(question, facts, ["登录调用链后半段需要结合 Service/Repository 命名和 import 图推断"], references)

    def _impact_answer(self, analysis: AnalysisResult, question: str) -> dict:
        candidates = [
            file
            for file in analysis.files
            if file.module_type in {"model", "schema", "repository", "service", "api", "test"}
        ]
        references = self._references_from_files(analysis, [file.path for file in candidates[:12]])
        facts = [
            "模型字段修改通常至少检查 model、schema、repository、service、api 和 test 层",
            f"当前项目模型数：{analysis.summary.model_count}，Schema 数：{analysis.summary.schema_count}",
        ]
        return self._response(question, facts, ["具体影响范围需要结合文件依赖图中的 import 边逐个确认"], references)

    def _keyword_answer(self, analysis: AnalysisResult, question: str, keywords: list[str]) -> dict:
        matches = self._search_source(analysis, keywords)
        references = [
            {"file": file_path, "line": line, "name": snippet.strip()[:80], "kind": "source"}
            for file_path, line, snippet in matches[:12]
        ]
        facts = [f"在 {len(matches)} 处源码位置找到相关关键词"] if matches else ["没有在源码中找到明确关键词"]
        return self._response(question, facts, ["关键词匹配只能说明相关位置，具体语义需要结合上下文阅读"], references)

    def _general_answer(self, analysis: AnalysisResult, question: str) -> dict:
        references = self._references_from_files(analysis, analysis.summary.core_modules[:8])
        facts = [
            f"项目类型：{analysis.summary.project_type}",
            f"技术栈：{', '.join(analysis.summary.tech_stack)}",
            f"已识别 {analysis.summary.route_count} 个路由、{analysis.summary.model_count} 个模型",
        ]
        return self._response(question, facts, ["当前问题未命中特定模板，先返回核心事实和建议阅读入口"], references)

    def _references_from_files(self, analysis: AnalysisResult, file_paths: list[str]) -> list[dict]:
        references: list[dict] = []
        seen: set[tuple[str, int, str]] = set()
        for file_path in file_paths:
            routes = [route for route in analysis.routes if route.file_path == file_path]
            symbols = [symbol for symbol in analysis.symbols if symbol.file_path == file_path]
            if not routes and not symbols:
                item = (file_path, 1, "文件级阅读")
                if item not in seen:
                    references.append({"file": file_path, "line": 1, "name": "文件级阅读", "kind": "file"})
                    seen.add(item)
            for route in routes:
                item = (route.file_path, route.line, route.handler)
                if item not in seen:
                    references.append(
                        {
                            "file": route.file_path,
                            "line": route.line,
                            "name": f"{route.http_method} {route.path} -> {route.handler}",
                            "kind": "route",
                        }
                    )
                    seen.add(item)
            for symbol in symbols[:6]:
                item = (symbol.file_path, symbol.start_line, symbol.name)
                if item not in seen:
                    references.append(
                        {
                            "file": symbol.file_path,
                            "line": symbol.start_line,
                            "name": symbol.name,
                            "kind": symbol.symbol_type,
                        }
                    )
                    seen.add(item)
        return references[:15]

    def _search_source(self, analysis: AnalysisResult, keywords: list[str]) -> list[tuple[str, int, str]]:
        root = Path(analysis.root_path)
        lowered_keywords = [keyword.lower() for keyword in keywords]
        matches: list[tuple[str, int, str]] = []
        for file in analysis.files:
            if not file.path.endswith(".py"):
                continue
            try:
                lines = (root / file.path).read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for index, line in enumerate(lines, start=1):
                if any(keyword in line.lower() for keyword in lowered_keywords):
                    matches.append((file.path, index, line))
        return matches

    def _contains(self, question: str, words: list[str]) -> bool:
        return any(word.lower() in question for word in words)

    def _response(self, question: str, facts: list[str], inferences: list[str], references: list[dict]) -> dict:
        return {
            "question": question,
            "answer": "\n".join(facts + [f"推断：{item}" for item in inferences]),
            "facts": facts,
            "inferences": inferences,
            "references": references,
        }

