from __future__ import annotations

from app.schemas.analysis import AnalysisResult, ModelInfo, SchemaInfo


class ModelAnalyzer:
    """模型分析入口，区分 SQLAlchemy 模型和 Pydantic Schema。"""

    def list_models(self, analysis: AnalysisResult) -> list[ModelInfo]:
        return analysis.models

    def list_schemas(self, analysis: AnalysisResult) -> list[SchemaInfo]:
        return analysis.schemas

