from __future__ import annotations

from pathlib import Path

from app.services.analysis_service import AnalysisService


def test_analysis_service_extracts_fastapi_facts() -> None:
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    analysis = AnalysisService().analyze("demo", repo_root)

    assert analysis.summary.project_type == "FastAPI 后端服务"
    assert "FastAPI" in analysis.summary.tech_stack
    assert "SQLAlchemy" in analysis.summary.tech_stack
    assert len(analysis.routes) >= 5
    assert any(route.path == "/login" and route.handler == "login" for route in analysis.routes)
    assert any(model.class_name == "OrderItem" for model in analysis.models)
    assert any(schema.class_name == "OrderCreate" for schema in analysis.schemas)
    assert analysis.dependencies
    assert any(edge.source_symbol == "login" and edge.target_symbol == "AuthService.login" for edge in analysis.call_edges)
    assert any(
        edge.source_symbol == "AuthService.login" and edge.target_symbol == "UserRepository.get_by_email"
        for edge in analysis.call_edges
    )
