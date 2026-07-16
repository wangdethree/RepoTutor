from __future__ import annotations

from pathlib import Path

from app.services.analysis_service import AnalysisService
from app.services.dependency_graph_service import DependencyGraphService


def test_dependency_graph_service_builds_filterable_nodes_and_edges() -> None:
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    analysis = AnalysisService().analyze("demo", repo_root)

    graph = DependencyGraphService().build(analysis)

    assert graph["summary"]["node_count"] == len(analysis.files)
    assert graph["summary"]["edge_count"] == len(analysis.dependencies)
    assert "api" in graph["summary"]["module_types"]
    assert graph["summary"]["core_node_count"] >= 1

    node_by_id = {node["id"]: node for node in graph["nodes"]}
    assert "app/main.py" in node_by_id
    assert node_by_id["app/main.py"]["is_core"] is True
    assert node_by_id["app/main.py"]["importance_score"] > 0

    edge = next(item for item in graph["edges"] if item["source"] == "app/main.py")
    assert edge["target"].startswith("app/")
    assert edge["edge_type"] == "imports"
    assert edge["evidence"]
