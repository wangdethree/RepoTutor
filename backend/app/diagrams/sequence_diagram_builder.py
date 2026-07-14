from __future__ import annotations

from app.schemas.analysis import AnalysisResult, DiagramArtifact


class SequenceDiagramBuilder:
    """根据首个核心路由生成业务时序图。"""

    def build(self, analysis: AnalysisResult) -> DiagramArtifact:
        route = analysis.routes[0] if analysis.routes else None
        title = f"{route.http_method} {route.path}" if route else "核心请求"
        handler = route.handler if route else "route_handler"
        lines = [
            "@startuml",
            f"title {title} 调用链",
            "actor Client",
            "participant Router",
            "participant Service",
            "participant Repository",
            "database Database",
            f"Client -> Router : {title}",
            f"Router -> Router : {handler}()",
            "Router -> Service : 调用业务逻辑",
            "Service -> Repository : 读写数据",
            "Repository -> Database : SQLAlchemy",
            "Database --> Repository : 数据结果",
            "Repository --> Service : 返回实体",
            "Service --> Router : 返回响应数据",
            "Router --> Client : HTTP Response",
            "@enduml",
        ]
        return DiagramArtifact(
            id="core-sequence",
            kind="sequence",
            title="核心业务时序图",
            format="plantuml",
            source="\n".join(lines),
            description="路由入口来自 AST，后续层级按扫描到的分层结构生成。",
        )

