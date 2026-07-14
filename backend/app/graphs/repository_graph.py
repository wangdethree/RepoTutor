from __future__ import annotations

from app.schemas.analysis import AnalysisResult, DiagramArtifact


class RepositoryGraphBuilder:
    """生成文件级依赖图，NetworkX 可在后续版本用于中心性分析。"""

    def build_mermaid(self, analysis: AnalysisResult) -> DiagramArtifact:
        node_ids: dict[str, str] = {}
        lines = ["flowchart LR"]
        for index, file in enumerate(analysis.files[:40], start=1):
            node_id = f"N{index}"
            node_ids[file.path] = node_id
            label = file.path.replace('"', "")
            lines.append(f'    {node_id}["{label}<br/>score={file.importance_score}"]')
        for edge in analysis.dependencies:
            if edge.source in node_ids and edge.target in node_ids:
                lines.append(f"    {node_ids[edge.source]} --> {node_ids[edge.target]}")
        return DiagramArtifact(
            id="file-dependency",
            kind="dependency",
            title="文件依赖图",
            format="mermaid",
            source="\n".join(lines),
            description="节点为真实文件，边来自 import 语句解析。",
        )

