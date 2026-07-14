from __future__ import annotations

from app.schemas.analysis import AnalysisResult, DiagramArtifact


class ArchitectureDiagramBuilder:
    """生成系统分层架构 Mermaid 图。"""

    def build(self, analysis: AnalysisResult) -> DiagramArtifact:
        modules = {file.module_type for file in analysis.files}
        lines = [
            "flowchart TB",
            "    Client[Client / Frontend]",
            "    API[FastAPI Router Layer]",
            "    Service[Service Layer]",
            "    Repository[Repository Layer]",
            "    Data[(SQLAlchemy / Database)]",
            "    Config[配置管理]",
            "    Auth[JWT / 认证]",
            "    Cache[(Redis / Cache)]",
            "    Client --> API",
        ]
        if "service" in modules:
            lines.append("    API --> Service")
        else:
            lines.append("    API -. 推断 .-> Service")
        if "repository" in modules:
            lines.append("    Service --> Repository")
        else:
            lines.append("    Service -. 推断 .-> Repository")
        if "model" in modules:
            lines.append("    Repository --> Data")
        else:
            lines.append("    Repository -. 推断 .-> Data")
        lines.extend(
            [
                "    Config -. 横切 .-> API",
                "    Auth -. 横切 .-> API",
                "    Cache -. 可选依赖 .-> Service",
            ]
        )
        return DiagramArtifact(
            id="layered-architecture",
            kind="architecture",
            title="系统分层架构图",
            format="mermaid",
            source="\n".join(lines),
            description="基于文件分层和技术栈生成，实线表示仓库结构确认，虚线表示常规 FastAPI 分层推断。",
        )


def build_all_diagrams(analysis: AnalysisResult) -> list[DiagramArtifact]:
    from app.diagrams.class_diagram_builder import ClassDiagramBuilder
    from app.diagrams.component_diagram_builder import ComponentDiagramBuilder
    from app.diagrams.deployment_diagram_builder import DeploymentDiagramBuilder
    from app.diagrams.er_diagram_builder import ERDiagramBuilder
    from app.diagrams.sequence_diagram_builder import SequenceDiagramBuilder
    from app.graphs.repository_graph import RepositoryGraphBuilder

    return [
        ArchitectureDiagramBuilder().build(analysis),
        ComponentDiagramBuilder().build(analysis),
        ClassDiagramBuilder().build(analysis),
        ERDiagramBuilder().build(analysis),
        SequenceDiagramBuilder().build(analysis),
        DeploymentDiagramBuilder().build(analysis),
        RepositoryGraphBuilder().build_mermaid(analysis),
    ]

