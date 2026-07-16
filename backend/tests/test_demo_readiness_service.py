from __future__ import annotations

from app.services.demo_readiness_service import DemoReadinessService


def test_demo_readiness_marks_pending_project_steps() -> None:
    payload = DemoReadinessService().build(
        project={"id": "project-1", "name": "Demo"},
        analysis=None,
        plan=None,
        diagrams=[],
        progress={"completion_rate": 0, "needs_review_lessons": 0},
        practice_progress=None,
        quiz_results=[],
        interview_readiness=None,
    )

    assert payload["readiness_score"] == 0
    assert payload["ready_for_demo"] is False
    assert payload["items"][0]["status"] == "TODO"
    assert payload["next_actions"]


def test_demo_readiness_marks_complete_demo_loop() -> None:
    payload = DemoReadinessService().build(
        project={"id": "project-1", "name": "Demo"},
        analysis={"summary": {"python_file_count": 8, "route_count": 4}},
        plan={"lessons": [{"id": "lesson-1"}]},
        diagrams=[{"id": "a"}, {"id": "b"}, {"id": "c"}],
        progress={"completion_rate": 80, "needs_review_lessons": 0},
        practice_progress={"completion_rate": 80, "total_tasks": 6},
        quiz_results=[{"score": 80}],
        interview_readiness={"readiness_score": 80},
    )

    assert payload["readiness_score"] == 100
    assert payload["ready_for_demo"] is True
    assert payload["completed_items"] == payload["total_items"]
