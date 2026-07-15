from __future__ import annotations

from app.schemas.analysis import AnalysisResult, CallEdge, RouteInfo, SymbolInfo


class CallChainService:
    """把函数级调用边整理为可教学的路由调用链。"""

    def build_route_chains(self, analysis: AnalysisResult, limit: int = 5) -> list[dict]:
        chains: list[dict] = []
        for route in analysis.routes[:limit]:
            chain = self.build_for_route(analysis, route)
            if chain:
                chains.append(chain)
        return chains

    def build_primary_chain(self, analysis: AnalysisResult) -> dict:
        if not analysis.routes:
            return self._empty_chain(analysis)
        return self.build_for_route(analysis, analysis.routes[0]) or self._empty_chain(analysis)

    def build_for_route(self, analysis: AnalysisResult, route: RouteInfo) -> dict | None:
        source_symbol = self._route_symbol(analysis, route)
        if not source_symbol:
            return None

        edges_by_source = self._edges_by_source(analysis.call_edges)
        steps = [
            {
                "file": route.file_path,
                "line": route.line,
                "symbol": source_symbol.qualified_name or source_symbol.name,
                "kind": "route",
                "label": f"{route.http_method} {route.path}",
            }
        ]
        call_edges: list[dict] = []
        current_key = self._symbol_key(source_symbol.file_path, source_symbol.qualified_name or source_symbol.name)
        visited = {current_key}

        for _ in range(5):
            edge = self._next_edge(edges_by_source.get(current_key, []))
            if not edge or not edge.target_file or not edge.target_symbol:
                break
            target_key = self._symbol_key(edge.target_file, edge.target_symbol)
            if target_key in visited:
                break
            visited.add(target_key)
            steps.append(
                {
                    "file": edge.target_file,
                    "line": edge.target_line,
                    "symbol": edge.target_symbol,
                    "kind": self._module_kind(analysis, edge.target_file),
                    "label": edge.target_symbol,
                }
            )
            call_edges.append(
                {
                    "source": edge.source_symbol,
                    "target": edge.target_symbol,
                    "file": edge.source_file,
                    "line": edge.call_line,
                    "expression": edge.call_expression,
                    "confidence": edge.confidence,
                    "evidence": edge.evidence,
                }
            )
            current_key = target_key

        return {
            "id": f"{route.http_method.lower()}-{route.path.strip('/').replace('/', '-') or 'root'}",
            "title": f"{route.http_method} {route.path} 调用链",
            "route": {
                "file": route.file_path,
                "line": route.line,
                "method": route.http_method,
                "path": route.path,
                "handler": route.handler,
            },
            "steps": steps,
            "edges": call_edges,
            "references": [
                {"file": step["file"], "line": step["line"], "name": step["symbol"], "kind": step["kind"]}
                for step in steps
            ],
        }

    def _route_symbol(self, analysis: AnalysisResult, route: RouteInfo) -> SymbolInfo | None:
        for symbol in analysis.symbols:
            if symbol.file_path == route.file_path and symbol.name == route.handler:
                return symbol
        return None

    def _edges_by_source(self, call_edges: list[CallEdge]) -> dict[str, list[CallEdge]]:
        grouped: dict[str, list[CallEdge]] = {}
        for edge in call_edges:
            if not edge.target_file or not edge.target_symbol:
                continue
            key = self._symbol_key(edge.source_file, edge.source_symbol)
            grouped.setdefault(key, []).append(edge)
        return grouped

    def _next_edge(self, edges: list[CallEdge]) -> CallEdge | None:
        if not edges:
            return None
        edge = sorted(edges, key=lambda item: (self._edge_priority(item), item.call_line))[0]
        if self._edge_priority(edge) >= 4:
            return None
        return edge

    def _edge_priority(self, edge: CallEdge) -> int:
        target = edge.target_file.lower()
        symbol = edge.target_symbol.lower()
        if "." not in edge.target_symbol:
            return 4
        if "/services/" in f"/{target}" or "service" in symbol:
            return 0
        if "/repositories/" in f"/{target}" or "repository" in symbol:
            return 1
        if "/models/" in f"/{target}":
            return 2
        return 3

    def _module_kind(self, analysis: AnalysisResult, file_path: str) -> str:
        for file in analysis.files:
            if file.path == file_path:
                return file.module_type
        return "source"

    def _symbol_key(self, file_path: str, symbol: str) -> str:
        return f"{file_path}::{symbol}"

    def _empty_chain(self, analysis: AnalysisResult) -> dict:
        first_file = analysis.files[0] if analysis.files else None
        references = []
        if first_file:
            references.append(
                {"file": first_file.path, "line": 1, "name": "核心文件", "kind": first_file.module_type}
            )
        return {
            "id": "no-route",
            "title": "未识别到路由调用链",
            "route": {},
            "steps": references,
            "edges": [],
            "references": references,
        }
