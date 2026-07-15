from __future__ import annotations

from app.schemas.analysis import AnalysisResult, DiagramArtifact
from app.services.call_chain_service import CallChainService


class SequenceDiagramBuilder:
    """根据首个核心路由生成业务时序图。"""

    def build(self, analysis: AnalysisResult) -> DiagramArtifact:
        chain = CallChainService().build_primary_chain(analysis)
        if chain["edges"]:
            return self._build_from_chain(chain)
        return self._build_fallback(analysis)

    def _build_from_chain(self, chain: dict) -> DiagramArtifact:
        title = chain["title"]
        lines = ["@startuml", f"title {title}", "actor Client"]
        aliases: dict[str, str] = {}
        for index, step in enumerate(chain["steps"], start=1):
            alias = f"P{index}"
            aliases[step["symbol"]] = alias
            participant = "participant"
            if step["kind"] == "repository":
                participant = "database"
            lines.append(f'{participant} "{step["symbol"]}" as {alias}')
        first_step = chain["steps"][0]
        lines.append(f"Client -> {aliases[first_step['symbol']]} : {first_step['label']}")
        for edge in chain["edges"]:
            source_alias = aliases.get(edge["source"])
            target_alias = aliases.get(edge["target"])
            if source_alias and target_alias:
                lines.append(f"{source_alias} -> {target_alias} : {edge['expression']}")
        for previous, current in zip(reversed(chain["steps"][1:]), reversed(chain["steps"][:-1])):
            lines.append(f"{aliases[previous['symbol']]} --> {aliases[current['symbol']]} : 返回")
        lines.append(f"{aliases[first_step['symbol']]} --> Client : HTTP Response")
        lines.append("@enduml")
        return DiagramArtifact(
            id="core-sequence",
            kind="sequence",
            title="核心业务时序图",
            format="plantuml",
            source="\n".join(lines),
            description="路由入口和后续调用来自 AST 函数调用解析，优先展示可追溯的真实调用边。",
        )

    def _build_fallback(self, analysis: AnalysisResult) -> DiagramArtifact:
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
