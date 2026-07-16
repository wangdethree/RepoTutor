from __future__ import annotations

import re

from app.schemas.analysis import AnalysisResult, CallEdge, CodeFile, RouteInfo, SymbolInfo


class ContextualQAService:
    """围绕具体文件、函数和 diff 生成可追溯的源码追问回答。"""

    def answer(
        self,
        analysis: AnalysisResult,
        question: str,
        file_path: str = "",
        symbol_name: str = "",
        plan: dict | None = None,
        diff_impact: dict | None = None,
    ) -> dict:
        normalized_question = question.strip()
        tokens = self._tokens(" ".join([normalized_question, file_path, symbol_name]))
        files_by_path = {file.path: file for file in analysis.files}
        diff_reasons = self._diff_path_reasons(diff_impact)
        related_files = self._related_files(analysis, file_path, tokens, diff_reasons)
        related_paths = {file["path"] for file in related_files}
        symbols = self._related_symbols(analysis, related_paths, tokens, symbol_name)
        routes = self._related_routes(analysis, related_paths, tokens)
        call_edges = self._related_call_edges(analysis, related_paths, symbols, tokens)
        lessons = self._related_lessons(plan, related_paths, tokens)
        references = self._references(analysis, related_paths, symbols, routes)
        facts = self._facts(
            analysis=analysis,
            question=normalized_question,
            requested_file=file_path,
            requested_symbol=symbol_name,
            related_files=related_files,
            symbols=symbols,
            routes=routes,
            diff_impact=diff_impact,
            files_by_path=files_by_path,
        )
        inferences = self._inferences(diff_impact, file_path, symbol_name, bool(references))

        return {
            "question": normalized_question,
            "scope": {
                "file_path": file_path,
                "symbol_name": symbol_name,
                "diff_attached": bool(diff_impact),
                "matched_file_count": len(related_files),
                "matched_symbol_count": len(symbols),
            },
            "answer": "\n".join(facts + [f"推断：{item}" for item in inferences]),
            "facts": facts,
            "inferences": inferences,
            "references": references,
            "related_files": related_files,
            "related_routes": routes,
            "related_lessons": lessons,
            "related_call_edges": call_edges,
            "source_checkpoints": self._source_checkpoints(related_files, symbols, routes, diff_impact),
            "diff_focus": self._diff_focus(diff_impact),
            "follow_up_questions": self._follow_up_questions(related_files, routes, symbols, diff_impact),
            "fact_checked": True,
            "generation_mode": "deterministic",
        }

    def _related_files(
        self,
        analysis: AnalysisResult,
        requested_path: str,
        tokens: set[str],
        diff_reasons: dict[str, str],
    ) -> list[dict]:
        files_by_path = {file.path: file for file in analysis.files}
        scored: dict[str, dict] = {}

        def add(path: str, score: int, reason: str) -> None:
            file = files_by_path.get(path)
            if not file:
                return
            current = scored.get(path)
            if current:
                current["score"] += score
                if reason not in current["reasons"]:
                    current["reasons"].append(reason)
                return
            scored[path] = {"file": file, "score": score, "reasons": [reason]}

        if requested_path:
            if requested_path in files_by_path:
                add(requested_path, 100, "用户指定文件")
            else:
                requested_lower = requested_path.lower()
                for file in analysis.files:
                    if requested_lower in file.path.lower() or self._same_stem(requested_lower, file.path.lower()):
                        add(file.path, 80, "用户指定文件的模糊匹配")

        for path, reason in diff_reasons.items():
            add(path, 70, reason)

        for file in analysis.files:
            haystack = f"{file.path} {file.module_type} {file.summary}".lower()
            matched_tokens = [token for token in tokens if token and token in haystack]
            if matched_tokens:
                add(file.path, 10 + len(matched_tokens), "问题关键词命中")

        if not scored:
            for path in analysis.summary.core_modules[:6]:
                add(path, 5, "核心模块兜底")
            for file in sorted(analysis.files, key=lambda item: item.importance_score, reverse=True)[:4]:
                add(file.path, 4, "重要文件兜底")

        ranked = sorted(
            scored.values(),
            key=lambda item: (-item["score"], -item["file"].importance_score, item["file"].path),
        )
        return [self._file_payload(item["file"], "；".join(item["reasons"])) for item in ranked[:10]]

    def _related_symbols(
        self,
        analysis: AnalysisResult,
        related_paths: set[str],
        tokens: set[str],
        requested_symbol: str,
    ) -> list[dict]:
        symbol_query = requested_symbol.lower().strip()
        scored: list[tuple[int, SymbolInfo]] = []
        for symbol in analysis.symbols:
            haystack = f"{symbol.name} {symbol.qualified_name} {symbol.signature} {symbol.docstring or ''}".lower()
            score = 0
            if symbol.file_path in related_paths:
                score += 8
            if symbol_query and symbol_query in haystack:
                score += 50
            score += sum(2 for token in tokens if token in haystack)
            if score > 0:
                scored.append((score, symbol))

        if not scored and related_paths:
            for symbol in analysis.symbols:
                if symbol.file_path in related_paths:
                    scored.append((1, symbol))

        payloads = [
            self._symbol_payload(symbol)
            for _score, symbol in sorted(scored, key=lambda item: (-item[0], item[1].file_path, item[1].start_line))[:12]
        ]
        return self._dedupe_payloads(payloads, ("file", "line", "name"))

    def _related_routes(self, analysis: AnalysisResult, related_paths: set[str], tokens: set[str]) -> list[dict]:
        scored: list[tuple[int, RouteInfo]] = []
        for route in analysis.routes:
            haystack = f"{route.http_method} {route.path} {route.handler} {route.file_path}".lower()
            score = 0
            if route.file_path in related_paths:
                score += 10
            score += sum(3 for token in tokens if token in haystack)
            if score > 0:
                scored.append((score, route))
        return [
            self._route_payload(route)
            for _score, route in sorted(scored, key=lambda item: (-item[0], item[1].file_path, item[1].line))[:10]
        ]

    def _related_call_edges(
        self,
        analysis: AnalysisResult,
        related_paths: set[str],
        symbols: list[dict],
        tokens: set[str],
    ) -> list[dict]:
        symbol_names = {symbol["name"].lower() for symbol in symbols}
        scored: list[tuple[int, CallEdge]] = []
        for edge in analysis.call_edges:
            haystack = " ".join(
                [
                    edge.source_file,
                    edge.source_symbol,
                    edge.target_name,
                    edge.target_file,
                    edge.target_symbol,
                    edge.call_expression,
                ]
            ).lower()
            score = 0
            if edge.source_file in related_paths or edge.target_file in related_paths:
                score += 8
            if edge.source_symbol.lower() in symbol_names or edge.target_symbol.lower() in symbol_names:
                score += 6
            score += sum(2 for token in tokens if token in haystack)
            if score > 0:
                scored.append((score, edge))

        edges: list[dict] = []
        for _score, edge in sorted(scored, key=lambda item: (-item[0], item[1].source_file, item[1].source_line))[:10]:
            edges.append(
                {
                    "source_file": edge.source_file,
                    "source_symbol": edge.source_symbol,
                    "source_line": edge.source_line,
                    "target_file": edge.target_file,
                    "target_symbol": edge.target_symbol or edge.target_name,
                    "target_line": edge.target_line,
                    "call_line": edge.call_line,
                    "call_expression": edge.call_expression,
                    "confidence": edge.confidence,
                    "evidence": edge.evidence,
                }
            )
        return edges

    def _related_lessons(self, plan: dict | None, related_paths: set[str], tokens: set[str]) -> list[dict]:
        if not plan:
            return []
        lessons: list[dict] = []
        for lesson in plan.get("lessons", []):
            matched_files = sorted(set(lesson.get("related_files", [])) & related_paths)
            title = lesson.get("title", "")
            keyword_hit = any(token in title.lower() for token in tokens)
            if matched_files or keyword_hit:
                lessons.append(
                    {
                        "lesson_id": lesson["id"],
                        "title": title,
                        "order_index": lesson["order_index"],
                        "matched_files": matched_files,
                        "reason": "命中源码范围" if matched_files else "命中问题关键词",
                    }
                )
        return sorted(lessons, key=lambda item: item["order_index"])[:8]

    def _references(
        self,
        analysis: AnalysisResult,
        related_paths: set[str],
        symbols: list[dict],
        routes: list[dict],
    ) -> list[dict]:
        references: list[dict] = []
        seen: set[tuple[str, int, str]] = set()

        def add(file: str, line: int, name: str, kind: str) -> None:
            item = (file, line, name)
            if item in seen:
                return
            references.append({"file": file, "line": line, "name": name, "kind": kind})
            seen.add(item)

        for route in routes:
            add(route["file"], route["line"], f"{route['method']} {route['path']} -> {route['handler']}", "route")
        for symbol in symbols:
            add(symbol["file"], symbol["line"], symbol["name"], symbol["kind"])
        for file_path in sorted(related_paths):
            if any(reference["file"] == file_path for reference in references):
                continue
            if any(file.path == file_path for file in analysis.files):
                add(file_path, 1, "文件级阅读", "file")
        return references[:15]

    def _facts(
        self,
        analysis: AnalysisResult,
        question: str,
        requested_file: str,
        requested_symbol: str,
        related_files: list[dict],
        symbols: list[dict],
        routes: list[dict],
        diff_impact: dict | None,
        files_by_path: dict[str, CodeFile],
    ) -> list[str]:
        facts = [f"问题：{question}"]
        if requested_file:
            if requested_file in files_by_path:
                file = files_by_path[requested_file]
                facts.append(
                    f"指定文件 {file.path} 属于 {file.module_type} 层，{file.line_count} 行，重要度 {file.importance_score}。"
                )
            else:
                facts.append(f"指定文件 {requested_file} 未在静态分析结果中精确命中，已尝试做模糊匹配。")
        if requested_symbol:
            facts.append(f"指定符号关键词：{requested_symbol}。")
        facts.append(f"当前静态分析识别到 {len(related_files)} 个相关文件、{len(symbols)} 个相关符号。")
        if related_files:
            files = "、".join(file["path"] for file in related_files[:4])
            facts.append(f"优先阅读范围：{files}。")
        if routes:
            route_text = "、".join(f"{route['method']} {route['path']}" for route in routes[:4])
            facts.append(f"相关 API 入口：{route_text}。")
        if diff_impact:
            summary = diff_impact.get("summary", {})
            facts.append(
                "已结合 diff 影响分析："
                f"变更文件 {summary.get('changed_file_count', 0)} 个，"
                f"受影响文件 {summary.get('impacted_file_count', 0)} 个，"
                f"风险 {summary.get('risk_level', 'LOW')}。"
            )
        else:
            facts.append(
                f"未提供 diff 时，本回答只基于当前项目静态事实库；项目共有 {analysis.summary.route_count} 个路由。"
            )
        return facts

    def _inferences(
        self,
        diff_impact: dict | None,
        requested_file: str,
        requested_symbol: str,
        has_references: bool,
    ) -> list[str]:
        inferences = []
        if requested_file or requested_symbol:
            inferences.append("文件和符号范围来自用户输入、路径匹配、函数/类签名和问题关键词共同排序。")
        if diff_impact:
            inferences.append("diff 传播范围来自 import 依赖图和同业务命名启发式，最终仍需用测试回归确认。")
        else:
            inferences.append("如果要回答“这次改动影响哪里”，建议同时粘贴 git diff。")
        if not has_references:
            inferences.append("当前没有足够源码引用，建议先重新分析项目或缩小到具体文件路径。")
        return inferences

    def _source_checkpoints(
        self,
        related_files: list[dict],
        symbols: list[dict],
        routes: list[dict],
        diff_impact: dict | None,
    ) -> list[dict]:
        checkpoints: list[dict] = []
        for file in related_files[:5]:
            checkpoints.append(
                {
                    "file": file["path"],
                    "line": 1,
                    "kind": "file",
                    "checkpoint": f"先确认该文件在 {file['module_type']} 层的职责，以及它被依赖 {file['imported_by']} 次的原因。",
                }
            )
        for symbol in symbols[:5]:
            checkpoints.append(
                {
                    "file": symbol["file"],
                    "line": symbol["line"],
                    "kind": "symbol",
                    "checkpoint": f"阅读 {symbol['name']} 的签名和内部调用，确认问题是否落在这个实现点。",
                }
            )
        for route in routes[:4]:
            checkpoints.append(
                {
                    "file": route["file"],
                    "line": route["line"],
                    "kind": "route",
                    "checkpoint": f"从 {route['method']} {route['path']} 入口复述请求如何进入处理函数 {route['handler']}。",
                }
            )
        if diff_impact:
            for file in diff_impact.get("impacted_files", [])[:3]:
                checkpoints.append(
                    {
                        "file": file["path"],
                        "line": 1,
                        "kind": "diff_impact",
                        "checkpoint": "该文件属于 diff 影响范围，检查调用方契约和回归测试是否覆盖。",
                    }
                )
        return self._dedupe_payloads(checkpoints, ("file", "line", "kind"))[:14]

    def _diff_focus(self, diff_impact: dict | None) -> dict | None:
        if not diff_impact:
            return None
        summary = diff_impact.get("summary", {})
        return {
            "risk_level": summary.get("risk_level", "LOW"),
            "changed_files": [file["path"] for file in diff_impact.get("changed_files", [])],
            "impacted_files": [file["path"] for file in diff_impact.get("impacted_files", [])],
            "related_route_count": len(diff_impact.get("related_routes", [])),
            "related_lesson_count": len(diff_impact.get("related_lessons", [])),
            "recommendations": diff_impact.get("recommendations", [])[:5],
        }

    def _follow_up_questions(
        self,
        related_files: list[dict],
        routes: list[dict],
        symbols: list[dict],
        diff_impact: dict | None,
    ) -> list[str]:
        questions = []
        if related_files:
            questions.append(f"{related_files[0]['path']} 被哪些模块依赖？")
            questions.append(f"如果修改 {related_files[0]['path']}，最小回归测试范围是什么？")
        if symbols:
            questions.append(f"{symbols[0]['name']} 的输入输出契约是什么？")
        if routes:
            questions.append(f"{routes[0]['method']} {routes[0]['path']} 的完整调用链怎么走？")
        if diff_impact:
            questions.append("这次 diff 为什么是当前风险等级？")
            questions.append("这次变更可以如何写进 PR 描述和面试复盘？")
        if not questions:
            questions.append("这个项目最应该先读哪几个核心模块？")
        return questions[:6]

    def _diff_path_reasons(self, diff_impact: dict | None) -> dict[str, str]:
        reasons: dict[str, str] = {}
        if not diff_impact:
            return reasons
        for file in diff_impact.get("changed_files", []):
            reasons[file["path"]] = "diff 变更文件"
        for file in diff_impact.get("impacted_files", []):
            reasons.setdefault(file["path"], f"diff 影响文件：{file.get('reason', '依赖传播')}")
        return reasons

    def _file_payload(self, file: CodeFile, reason: str) -> dict:
        return {
            "path": file.path,
            "module_type": file.module_type,
            "line_count": file.line_count,
            "importance_score": file.importance_score,
            "imported_by": file.imported_by,
            "summary": file.summary,
            "reason": reason,
        }

    def _symbol_payload(self, symbol: SymbolInfo) -> dict:
        return {
            "file": symbol.file_path,
            "line": symbol.start_line,
            "end_line": symbol.end_line,
            "name": symbol.name,
            "qualified_name": symbol.qualified_name,
            "kind": symbol.symbol_type,
            "signature": symbol.signature,
            "docstring": symbol.docstring or "",
        }

    def _route_payload(self, route: RouteInfo) -> dict:
        return {
            "method": route.http_method,
            "path": route.path,
            "handler": route.handler,
            "file": route.file_path,
            "line": route.line,
            "response_model": route.response_model or "",
            "dependencies": route.dependencies,
        }

    def _tokens(self, text: str) -> set[str]:
        raw_tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_./-]*", text.lower())
        stop_words = {"the", "and", "for", "with", "this", "that", "what", "how", "why"}
        return {token for token in raw_tokens if len(token) >= 3 and token not in stop_words}

    def _same_stem(self, query: str, path: str) -> bool:
        query_stem = query.rsplit("/", maxsplit=1)[-1].removesuffix(".py")
        path_stem = path.rsplit("/", maxsplit=1)[-1].removesuffix(".py")
        return bool(query_stem and query_stem == path_stem)

    def _dedupe_payloads(self, payloads: list[dict], keys: tuple[str, ...]) -> list[dict]:
        deduped = []
        seen = set()
        for payload in payloads:
            marker = tuple(payload.get(key) for key in keys)
            if marker in seen:
                continue
            deduped.append(payload)
            seen.add(marker)
        return deduped
