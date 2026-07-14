from __future__ import annotations

import re

from app.schemas.analysis import AnalysisResult, DiagramArtifact


class ERDiagramBuilder:
    """生成 Mermaid ER 图，字段和外键来自模型 AST。"""

    def build(self, analysis: AnalysisResult) -> DiagramArtifact:
        lines = ["erDiagram"]
        for model in analysis.models[:30]:
            table = self._table_name(model.table_name or model.class_name)
            lines.append(f"    {table} {{")
            for field in model.fields[:20]:
                field_type = self._normalize_type(field.field_type)
                marker = " PK" if field.is_primary_key else ""
                marker += " FK" if field.foreign_key else ""
                lines.append(f"        {field_type} {field.name}{marker}")
            lines.append("    }")
        for model in analysis.models:
            source = self._table_name(model.table_name or model.class_name)
            for field in model.fields:
                if not field.foreign_key:
                    continue
                target = self._table_name(field.foreign_key.split(".", 1)[0])
                lines.append(f"    {target} ||--o{{ {source} : {field.name}")
        return DiagramArtifact(
            id="database-er",
            kind="er",
            title="数据库 ER 图",
            format="mermaid",
            source="\n".join(lines),
            description="表、字段、主键和外键来自 SQLAlchemy 模型静态分析。",
        )

    def _table_name(self, value: str) -> str:
        cleaned = re.sub(r"[^0-9A-Za-z_]", "_", value)
        return cleaned.upper()

    def _normalize_type(self, value: str) -> str:
        lowered = value.lower()
        if "int" in lowered:
            return "int"
        if "bool" in lowered:
            return "boolean"
        if "date" in lowered or "time" in lowered:
            return "datetime"
        if "float" in lowered or "numeric" in lowered:
            return "float"
        return "string"

