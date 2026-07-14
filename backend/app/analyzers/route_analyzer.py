from __future__ import annotations

from app.schemas.analysis import AnalysisResult, RouteInfo


class RouteAnalyzer:
    """路由分析入口，当前复用 AST 已提取的 FastAPI 装饰器事实。"""

    def list_routes(self, analysis: AnalysisResult) -> list[RouteInfo]:
        return analysis.routes

