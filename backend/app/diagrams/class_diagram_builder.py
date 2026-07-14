from __future__ import annotations

from app.schemas.analysis import AnalysisResult, DiagramArtifact


class ClassDiagramBuilder:
    """生成核心模型和 Schema 的 PlantUML 类图。"""

    def build(self, analysis: AnalysisResult) -> DiagramArtifact:
        lines = ["@startuml", "skinparam classAttributeIconSize 0"]
        for model in analysis.models[:20]:
            lines.append(f"class {model.class_name} {{")
            for field in model.fields[:12]:
                suffix = " <<PK>>" if field.is_primary_key else ""
                field_type = field.field_type.replace('"', "")
                lines.append(f"  +{field.name}: {field_type}{suffix}")
            lines.append("}")
        for schema in analysis.schemas[:20]:
            lines.append(f"class {schema.class_name} <<Pydantic>> {{")
            for field in schema.fields[:12]:
                lines.append(f"  +{field.name}: {field.field_type}")
            lines.append("}")
        for model in analysis.models:
            for field in model.fields:
                if field.foreign_key:
                    target = field.foreign_key.split(".", 1)[0].title().replace("_", "")
                    lines.append(f"{model.class_name} --> {target} : {field.name}")
        lines.append("@enduml")
        return DiagramArtifact(
            id="uml-class",
            kind="class",
            title="UML 类图",
            format="plantuml",
            source="\n".join(lines),
            description="展示 AST 确认的 SQLAlchemy 模型和 Pydantic Schema。",
        )

