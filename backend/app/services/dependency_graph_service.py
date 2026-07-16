from __future__ import annotations

from app.schemas.analysis import AnalysisResult


class DependencyGraphService:
    """把文件级 import 依赖转换为前端可筛选的 nodes / edges 数据。"""

    def build(self, analysis: AnalysisResult) -> dict:
        files_by_path = {file.path: file for file in analysis.files}
        core_modules = set(analysis.summary.core_modules)
        outgoing_count = self._outgoing_count(analysis)

        nodes = [
            {
                "id": file.path,
                "label": file.path,
                "module_type": file.module_type,
                "line_count": file.line_count,
                "importance_score": file.importance_score,
                "imported_by": file.imported_by,
                "imports_count": outgoing_count.get(file.path, 0),
                "is_core": file.path in core_modules,
            }
            for file in analysis.files
        ]
        edges = [
            {
                "id": f"{edge.source}->{edge.target}:{index}",
                "source": edge.source,
                "target": edge.target,
                "edge_type": edge.edge_type,
                "confidence": edge.confidence,
                "evidence": edge.evidence,
            }
            for index, edge in enumerate(analysis.dependencies, start=1)
            if edge.source in files_by_path and edge.target in files_by_path
        ]

        return {
            "summary": {
                "node_count": len(nodes),
                "edge_count": len(edges),
                "module_types": sorted({node["module_type"] for node in nodes}),
                "core_node_count": len([node for node in nodes if node["is_core"]]),
                "max_importance_score": max((node["importance_score"] for node in nodes), default=0),
                "max_imported_by": max((node["imported_by"] for node in nodes), default=0),
            },
            "nodes": sorted(nodes, key=lambda node: (-node["importance_score"], node["id"])),
            "edges": sorted(edges, key=lambda edge: (edge["source"], edge["target"])),
        }

    def _outgoing_count(self, analysis: AnalysisResult) -> dict[str, int]:
        counts: dict[str, int] = {}
        for edge in analysis.dependencies:
            counts[edge.source] = counts.get(edge.source, 0) + 1
        return counts
