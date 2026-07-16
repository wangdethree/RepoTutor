from __future__ import annotations

from collections import deque

from app.schemas.analysis import AnalysisResult


class DiffImpactService:
    """基于 git diff 文本和静态依赖图生成修改影响分析。"""

    def analyze(self, analysis: AnalysisResult, diff_text: str, plan: dict | None = None) -> dict:
        changed_paths = self._extract_changed_paths(diff_text)
        files_by_path = {file.path: file for file in analysis.files}
        known_changed = [path for path in changed_paths if path in files_by_path]
        reverse_edges = self._reverse_edges(analysis)

        domain_impacts = self._domain_related_files(known_changed, files_by_path)
        impacted = self._collect_impacted_files(known_changed, reverse_edges, domain_impacts)
        impacted_paths = {item["path"] for item in impacted}
        focus_paths = set(known_changed) | impacted_paths

        changed_files = [self._changed_file_payload(path, files_by_path) for path in changed_paths]
        impacted_files = [self._file_impact_payload(item, files_by_path) for item in impacted]
        dependent_edges = self._dependent_edges(analysis, focus_paths, set(known_changed))

        result = {
            "summary": self._summary(changed_files, impacted_files, dependent_edges),
            "changed_files": changed_files,
            "impacted_files": impacted_files,
            "dependent_edges": dependent_edges,
            "outgoing_dependencies": self._outgoing_dependencies(analysis, set(known_changed)),
            "related_routes": self._related_routes(analysis, focus_paths),
            "related_lessons": self._related_lessons(plan, focus_paths) if plan else [],
            "recommendations": [],
        }
        result["recommendations"] = self._recommendations(result)
        return result

    def _extract_changed_paths(self, diff_text: str) -> list[str]:
        paths: list[str] = []
        current_old = ""
        current_new = ""
        for line in diff_text.splitlines():
            if line.startswith("diff --git "):
                parts = line.split()
                if len(parts) >= 4:
                    current_old = self._normalize_diff_path(parts[2])
                    current_new = self._normalize_diff_path(parts[3])
                    self._append_path(paths, current_new or current_old)
            elif line.startswith("--- "):
                current_old = self._normalize_diff_path(line[4:].strip())
            elif line.startswith("+++ "):
                current_new = self._normalize_diff_path(line[4:].strip())
                self._append_path(paths, current_new or current_old)
        return paths

    def _normalize_diff_path(self, value: str) -> str:
        cleaned = value.strip().strip('"')
        if cleaned == "/dev/null":
            return ""
        if cleaned.startswith(("a/", "b/")):
            return cleaned[2:]
        return cleaned

    def _append_path(self, paths: list[str], path: str) -> None:
        if path and path not in paths:
            paths.append(path)

    def _reverse_edges(self, analysis: AnalysisResult) -> dict[str, list[dict]]:
        reverse: dict[str, list[dict]] = {}
        for edge in analysis.dependencies:
            reverse.setdefault(edge.target, []).append(
                {
                    "source": edge.source,
                    "target": edge.target,
                    "edge_type": edge.edge_type,
                    "confidence": edge.confidence,
                    "evidence": edge.evidence,
                }
            )
        return reverse

    def _collect_impacted_files(
        self,
        changed_paths: list[str],
        reverse_edges: dict[str, list[dict]],
        initial_impacts: list[dict] | None = None,
        max_depth: int = 2,
    ) -> list[dict]:
        impacted: list[dict] = []
        visited = set(changed_paths)
        queue = deque((path, 0, path) for path in changed_paths)
        for item in initial_impacts or []:
            if item["path"] in visited:
                continue
            visited.add(item["path"])
            impacted.append(item)
            queue.append((item["path"], item["depth"], item["changed_root"]))
        while queue:
            current, depth, root = queue.popleft()
            if depth >= max_depth:
                continue
            for edge in reverse_edges.get(current, []):
                source = edge["source"]
                if source in visited:
                    continue
                next_depth = depth + 1
                visited.add(source)
                impacted.append(
                    {
                        "path": source,
                        "depth": next_depth,
                        "changed_root": root,
                        "reason": f"{source} imports {current}",
                        "evidence": edge["evidence"],
                    }
                )
                queue.append((source, next_depth, root))
        return sorted(impacted, key=lambda item: (item["depth"], item["path"]))

    def _domain_related_files(self, changed_paths: list[str], files_by_path: dict) -> list[dict]:
        impacts: list[dict] = []
        for changed_path in changed_paths:
            tokens = self._domain_tokens(changed_path)
            if not tokens:
                continue
            for candidate_path in files_by_path:
                if candidate_path == changed_path:
                    continue
                candidate_tokens = self._domain_tokens(candidate_path)
                if not tokens & candidate_tokens:
                    continue
                impacts.append(
                    {
                        "path": candidate_path,
                        "depth": 1,
                        "changed_root": changed_path,
                        "reason": f"{candidate_path} 与 {changed_path} 命中同一业务命名",
                        "evidence": "heuristic: same domain token",
                    }
                )
        deduped: dict[str, dict] = {}
        for item in impacts:
            deduped.setdefault(item["path"], item)
        return sorted(deduped.values(), key=lambda item: item["path"])

    def _domain_tokens(self, path: str) -> set[str]:
        stem = path.rsplit("/", maxsplit=1)[-1]
        if stem.endswith(".py"):
            stem = stem[:-3]
        for suffix in ("_repository", "_service", "_schema", "_model", "_api"):
            if stem.endswith(suffix):
                stem = stem[: -len(suffix)]
        tokens = {part for part in stem.replace("-", "_").split("_") if len(part) >= 3}
        if stem and len(stem) >= 3:
            tokens.add(stem)
        return tokens

    def _changed_file_payload(self, path: str, files_by_path: dict) -> dict:
        file = files_by_path.get(path)
        if not file:
            return {
                "path": path,
                "known": False,
                "module_type": "unknown",
                "importance_score": 0,
                "imported_by": 0,
                "line_count": 0,
            }
        return {
            "path": path,
            "known": True,
            "module_type": file.module_type,
            "importance_score": file.importance_score,
            "imported_by": file.imported_by,
            "line_count": file.line_count,
        }

    def _file_impact_payload(self, item: dict, files_by_path: dict) -> dict:
        file = files_by_path[item["path"]]
        return {
            **item,
            "module_type": file.module_type,
            "importance_score": file.importance_score,
            "imported_by": file.imported_by,
            "line_count": file.line_count,
        }

    def _dependent_edges(self, analysis: AnalysisResult, focus_paths: set[str], changed_paths: set[str]) -> list[dict]:
        edges: list[dict] = []
        for edge in analysis.dependencies:
            if edge.target in changed_paths and edge.source in focus_paths:
                edges.append(
                    {
                        "source": edge.source,
                        "target": edge.target,
                        "edge_type": edge.edge_type,
                        "confidence": edge.confidence,
                        "evidence": edge.evidence,
                    }
                )
        return sorted(edges, key=lambda item: (item["target"], item["source"]))

    def _outgoing_dependencies(self, analysis: AnalysisResult, changed_paths: set[str]) -> list[dict]:
        return [
            {
                "source": edge.source,
                "target": edge.target,
                "edge_type": edge.edge_type,
                "confidence": edge.confidence,
                "evidence": edge.evidence,
            }
            for edge in analysis.dependencies
            if edge.source in changed_paths
        ]

    def _related_routes(self, analysis: AnalysisResult, focus_paths: set[str]) -> list[dict]:
        routes = [
            {
                "method": route.http_method,
                "path": route.path,
                "handler": route.handler,
                "file": route.file_path,
                "line": route.line,
            }
            for route in analysis.routes
            if route.file_path in focus_paths
        ]
        return sorted(routes, key=lambda item: (item["file"], item["line"]))

    def _related_lessons(self, plan: dict | None, focus_paths: set[str]) -> list[dict]:
        lessons: list[dict] = []
        for lesson in (plan or {}).get("lessons", []):
            matched_files = sorted(set(lesson.get("related_files", [])) & focus_paths)
            if matched_files:
                lessons.append(
                    {
                        "id": lesson["id"],
                        "title": lesson["title"],
                        "order_index": lesson["order_index"],
                        "matched_files": matched_files,
                    }
                )
        return lessons

    def _summary(self, changed_files: list[dict], impacted_files: list[dict], dependent_edges: list[dict]) -> dict:
        known_changed = [file for file in changed_files if file["known"]]
        high_importance_changes = [file for file in known_changed if file["importance_score"] >= 60]
        risk_level = "LOW"
        if high_importance_changes or len(impacted_files) >= 5:
            risk_level = "HIGH"
        elif dependent_edges or len(impacted_files) >= 2:
            risk_level = "MEDIUM"
        return {
            "changed_file_count": len(changed_files),
            "known_changed_file_count": len(known_changed),
            "unknown_changed_file_count": len(changed_files) - len(known_changed),
            "impacted_file_count": len(impacted_files),
            "dependent_edge_count": len(dependent_edges),
            "risk_level": risk_level,
        }

    def _recommendations(self, result: dict) -> list[str]:
        summary = result["summary"]
        recommendations = []
        if summary["unknown_changed_file_count"]:
            recommendations.append("有变更文件不在静态分析结果中，建议重新导入或重新分析项目。")
        if result["related_routes"]:
            recommendations.append("优先回归相关路由的请求处理流程，确认输入、权限、业务调用和响应结构。")
        if result["related_lessons"]:
            recommendations.append("建议复习命中的课程，再对照源码确认修改影响。")
        if result["outgoing_dependencies"]:
            recommendations.append("变更文件依赖其他模块，检查这些下游依赖的接口契约是否仍然满足。")
        if not recommendations:
            recommendations.append("当前 diff 没有命中已知源码文件，可以先确认路径是否来自本项目。")
        if summary["risk_level"] == "HIGH":
            recommendations.append("影响范围较高，提交前建议补充或运行相关测试。")
        return recommendations
