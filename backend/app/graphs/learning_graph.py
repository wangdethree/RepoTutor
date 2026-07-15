from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict


class RepoTutorState(TypedDict, total=False):
    run_id: str
    project_id: str
    root_path: str
    analysis: dict
    repository_summary: dict
    learner_profile: dict
    architecture_views: list[dict]
    learning_plan: dict
    current_lesson_id: str | None
    current_lesson: dict | None
    quiz: dict | None
    answers: list[dict]
    evaluation: dict | None
    mastery: dict[str, float]
    next_action: str | None


def route_next_action(score: int) -> str:
    """V1 掌握度路由规则，后续可替换为 LangGraph 条件边。"""

    if score >= 80:
        return "NEXT_LESSON"
    if score >= 60:
        return "REVIEW_LATER"
    return "REMEDIAL_LESSON"


def build_onboarding_graph(node_handlers: dict[str, Callable[[RepoTutorState], dict[str, Any]]]):
    """构建项目导入后的 LangGraph 工作流。

    LangGraph 作为可选运行依赖在这里延迟导入，让离线静态分析脚本不被 Web/Agent 依赖拖住。
    """

    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(RepoTutorState)
    graph.add_node("analyze_repository", node_handlers["analyze_repository"])
    graph.add_node("generate_architecture_views", node_handlers["generate_architecture_views"])
    graph.add_node("load_learner_profile", node_handlers["load_learner_profile"])
    graph.add_node("generate_curriculum", node_handlers["generate_curriculum"])

    graph.add_edge(START, "analyze_repository")
    graph.add_edge("analyze_repository", "generate_architecture_views")
    graph.add_edge("generate_architecture_views", "load_learner_profile")
    graph.add_edge("load_learner_profile", "generate_curriculum")
    graph.add_edge("generate_curriculum", END)
    return graph.compile()
