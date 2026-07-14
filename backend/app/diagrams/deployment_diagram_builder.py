from __future__ import annotations

from app.schemas.analysis import AnalysisResult, DiagramArtifact


class DeploymentDiagramBuilder:
    """根据技术栈推断部署组件，虚线表示可选组件。"""

    def build(self, analysis: AnalysisResult) -> DiagramArtifact:
        stack = set(analysis.summary.tech_stack)
        lines = [
            "flowchart LR",
            "    User[用户浏览器]",
            "    Nginx[Nginx / 反向代理]",
            "    App[FastAPI / Uvicorn]",
            "    Logs[日志与监控]",
            "    User --> Nginx --> App",
            "    App -. 写入 .-> Logs",
        ]
        if "Redis" in stack:
            lines.append("    App --> Redis[(Redis)]")
        else:
            lines.append("    App -. 可选缓存 .-> Redis[(Redis)]")
        if "SQLAlchemy" in stack:
            lines.append("    App --> DB[(PostgreSQL / MySQL / SQLite)]")
        else:
            lines.append("    App -. 可选数据库 .-> DB[(Database)]")
        if "Celery" in stack:
            lines.append("    App --> Worker[Celery Worker]")
            lines.append("    Worker --> Redis")
        return DiagramArtifact(
            id="deployment",
            kind="deployment",
            title="部署图",
            format="mermaid",
            source="\n".join(lines),
            description="根据项目依赖中的 Redis、SQLAlchemy、Celery 等信号生成。",
        )

