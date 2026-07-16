from __future__ import annotations

from app.services.project_dashboard_service import ProjectDashboardService


def test_project_dashboard_scores_ready_project() -> None:
    payload = ProjectDashboardService().build(
        project={"id": "project-1", "name": "Demo"},
        analysis={
            "summary": {"python_file_count": 8, "route_count": 4, "model_count": 2},
            "dependencies": [{"source": "a", "target": "b"}],
            "call_edges": [{"source_file": "a", "target_name": "b"}],
        },
        plan={"lessons": [{"id": "lesson-1"}]},
        progress={"completion_rate": 90, "next_action": "PLAN_COMPLETED"},
        practice_progress={"completion_rate": 90, "remaining_tasks": 0},
        interview_readiness={"readiness_score": 85},
        demo_readiness={"readiness_score": 90, "next_actions": []},
        improvement_suggestions={
            "priority_counts": {"HIGH": 0, "MEDIUM": 1, "LOW": 1},
            "next_actions": ["补一条契约测试。"],
        },
    )

    assert payload["overall_score"] >= 80
    assert payload["status"] == "READY"
    assert len(payload["dimensions"]) == 6
    assert payload["next_actions"]


def test_project_dashboard_marks_uninitialized_project() -> None:
    payload = ProjectDashboardService().build(
        project={"id": "project-1", "name": "Demo"},
        analysis=None,
        plan=None,
        progress={"completion_rate": 0, "next_action": ""},
        practice_progress=None,
        interview_readiness=None,
        demo_readiness={"readiness_score": 0, "next_actions": ["先完成项目分析。"]},
        improvement_suggestions={
            "priority_counts": {"HIGH": 0, "MEDIUM": 0, "LOW": 0},
            "next_actions": [],
        },
    )

    assert payload["status"] == "NEEDS_SETUP"
    assert payload["dimensions"][0]["score"] == 0
    assert payload["next_actions"] == ["先完成项目分析。"]
