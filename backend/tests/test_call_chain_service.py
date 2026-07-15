from __future__ import annotations

from pathlib import Path

from app.diagrams.sequence_diagram_builder import SequenceDiagramBuilder
from app.services.analysis_service import AnalysisService
from app.services.call_chain_service import CallChainService


def test_call_chain_service_builds_route_to_repository_path() -> None:
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    analysis = AnalysisService().analyze("demo", repo_root)

    chain = CallChainService().build_primary_chain(analysis)

    assert chain["title"] == "POST /login 调用链"
    symbols = [step["symbol"] for step in chain["steps"]]
    assert symbols == ["login", "AuthService.login", "UserRepository.get_by_email"]
    assert [edge["expression"] for edge in chain["edges"]] == [
        "service.login(payload.email, payload.password)",
        "self.user_repository.get_by_email(email)",
    ]


def test_sequence_diagram_uses_resolved_call_chain() -> None:
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    analysis = AnalysisService().analyze("demo", repo_root)

    diagram = SequenceDiagramBuilder().build(analysis)

    assert diagram.id == "core-sequence"
    assert "AuthService.login" in diagram.source
    assert "UserRepository.get_by_email" in diagram.source
    assert "service.login(payload.email, payload.password)" in diagram.source
