from __future__ import annotations

from app.schemas.analysis import AnalysisResult, DiagramArtifact


class ComponentDiagramBuilder:
    """生成 PlantUML 组件图，展示模块间依赖。"""

    def build(self, analysis: AnalysisResult) -> DiagramArtifact:
        component_names = {
            "api": "API Gateway",
            "service": "Service Layer",
            "repository": "Repository Layer",
            "model": "Domain Model",
            "schema": "Pydantic Schema",
            "core": "Core Config",
        }
        modules = {file.module_type for file in analysis.files}
        lines = ["@startuml", "skinparam componentStyle rectangle"]
        for module, label in component_names.items():
            if module in modules:
                lines.append(f'component "{label}" as {module}')
        if "api" in modules and "service" in modules:
            lines.append("api --> service : 调用")
        if "service" in modules and "repository" in modules:
            lines.append("service --> repository : 调用")
        if "repository" in modules and "model" in modules:
            lines.append("repository --> model : 使用")
        if "api" in modules and "schema" in modules:
            lines.append("api --> schema : 请求/响应")
        if "core" in modules:
            for module in sorted(modules & {"api", "service", "repository"}):
                lines.append(f"{module} ..> core : 配置")
        lines.append("@enduml")
        return DiagramArtifact(
            id="uml-component",
            kind="component",
            title="UML 组件图",
            format="plantuml",
            source="\n".join(lines),
            description="组件来自扫描到的真实目录分层，关系来自分层约定和 import 图。",
        )

