from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CodeFile:
    path: str
    module_type: str
    line_count: int
    imports: list[str] = field(default_factory=list)
    imported_by: int = 0
    importance_score: int = 0
    summary: str = ""


@dataclass
class SymbolInfo:
    file_path: str
    name: str
    symbol_type: str
    start_line: int
    end_line: int
    signature: str
    docstring: str | None
    decorators: list[str] = field(default_factory=list)


@dataclass
class RouteInfo:
    file_path: str
    http_method: str
    path: str
    handler: str
    line: int
    response_model: str | None = None
    dependencies: list[str] = field(default_factory=list)


@dataclass
class ModelField:
    name: str
    field_type: str
    is_primary_key: bool = False
    foreign_key: str | None = None
    default: str | None = None


@dataclass
class ModelInfo:
    file_path: str
    class_name: str
    table_name: str | None
    line: int
    fields: list[ModelField] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)


@dataclass
class SchemaField:
    name: str
    field_type: str
    required: bool = True
    default: str | None = None


@dataclass
class SchemaInfo:
    file_path: str
    class_name: str
    line: int
    fields: list[SchemaField] = field(default_factory=list)


@dataclass
class DependencyEdge:
    source: str
    target: str
    edge_type: str = "imports"
    confidence: float = 1.0
    evidence: str = ""


@dataclass
class DiagramArtifact:
    id: str
    kind: str
    title: str
    format: str
    source: str
    description: str


@dataclass
class ProjectSummary:
    project_type: str
    tech_stack: list[str]
    file_count: int
    python_file_count: int
    line_count: int
    route_count: int
    model_count: int
    schema_count: int
    difficulty: str
    estimated_days: int
    core_modules: list[str]


@dataclass
class AnalysisResult:
    project_id: str
    root_path: str
    summary: ProjectSummary
    files: list[CodeFile] = field(default_factory=list)
    symbols: list[SymbolInfo] = field(default_factory=list)
    routes: list[RouteInfo] = field(default_factory=list)
    models: list[ModelInfo] = field(default_factory=list)
    schemas: list[SchemaInfo] = field(default_factory=list)
    dependencies: list[DependencyEdge] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def from_dict(payload: dict[str, Any]) -> AnalysisResult:
    """把 SQLite 中的 JSON 恢复为 dataclass，方便服务层继续使用。"""

    summary = ProjectSummary(**payload["summary"])
    files = [CodeFile(**item) for item in payload.get("files", [])]
    symbols = [SymbolInfo(**item) for item in payload.get("symbols", [])]
    routes = [RouteInfo(**item) for item in payload.get("routes", [])]
    models = [
        ModelInfo(
            **{
                **item,
                "fields": [ModelField(**field) for field in item.get("fields", [])],
            }
        )
        for item in payload.get("models", [])
    ]
    schemas = [
        SchemaInfo(
            **{
                **item,
                "fields": [SchemaField(**field) for field in item.get("fields", [])],
            }
        )
        for item in payload.get("schemas", [])
    ]
    dependencies = [DependencyEdge(**item) for item in payload.get("dependencies", [])]
    return AnalysisResult(
        project_id=payload["project_id"],
        root_path=payload["root_path"],
        summary=summary,
        files=files,
        symbols=symbols,
        routes=routes,
        models=models,
        schemas=schemas,
        dependencies=dependencies,
    )

