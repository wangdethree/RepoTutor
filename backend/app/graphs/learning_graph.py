from __future__ import annotations

from typing import TypedDict


class RepoTutorState(TypedDict, total=False):
    project_id: str
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

