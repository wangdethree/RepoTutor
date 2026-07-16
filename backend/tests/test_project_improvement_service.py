from __future__ import annotations

from app.services.project_improvement_service import ProjectImprovementService


def test_project_improvement_prioritizes_missing_tests_for_routed_project() -> None:
    payload = ProjectImprovementService().build(
        project={"id": "project-1", "name": "Demo"},
        analysis={
            "summary": {
                "python_file_count": 12,
                "route_count": 4,
                "model_count": 0,
                "tech_stack": ["FastAPI"],
                "core_modules": ["app/api/routes.py", "app/services/user_service.py"],
            },
            "files": [
                {
                    "path": "app/api/routes.py",
                    "module_type": "api",
                    "importance_score": 90,
                },
                {
                    "path": "app/services/user_service.py",
                    "module_type": "service",
                    "importance_score": 70,
                },
            ],
            "routes": [
                {"file_path": "app/api/routes.py", "response_model": ""}
                for _ in range(4)
            ],
        },
        plan=None,
        progress={"completion_rate": 0, "lessons": []},
        practice_progress=None,
        quiz_results=[],
    )

    assert payload["priority_counts"]["HIGH"] >= 1
    assert payload["highest_priority"] == "HIGH"
    assert payload["suggestions"][0]["id"] in {"learning_plan_missing", "testing_baseline"}
    assert any(item["id"] == "testing_baseline" for item in payload["suggestions"])
    assert all(item["interview_talking_point"] for item in payload["suggestions"])
    assert payload["next_actions"]


def test_project_improvement_surfaces_learning_and_practice_gaps() -> None:
    payload = ProjectImprovementService().build(
        project={"id": "project-1", "name": "Demo"},
        analysis={
            "summary": {
                "python_file_count": 6,
                "route_count": 1,
                "model_count": 0,
                "tech_stack": ["FastAPI", "pytest"],
                "core_modules": ["app/main.py", "app/api/routes.py", "app/services/report.py"],
            },
            "files": [
                {"path": "tests/test_app.py", "module_type": "test", "importance_score": 30},
            ],
            "routes": [
                {"file_path": "app/api/routes.py", "response_model": "ProjectOut"},
            ],
        },
        plan={
            "lessons": [
                {
                    "id": "lesson-1",
                    "title": "入口与路由",
                    "order_index": 1,
                    "related_files": ["app/api/routes.py"],
                }
            ]
        },
        progress={
            "completion_rate": 40,
            "lessons": [
                {
                    "id": "lesson-1",
                    "title": "入口与路由",
                    "order_index": 1,
                    "status": "NEEDS_REVIEW",
                    "related_files": ["app/api/routes.py"],
                }
            ],
        },
        practice_progress={
            "completion_rate": 30,
            "remaining_tasks": 2,
            "lessons": [
                {
                    "lesson_id": "lesson-1",
                    "lesson_title": "入口与路由",
                    "order_index": 1,
                    "pending_tasks": ["定位路由入口"],
                }
            ],
        },
        quiz_results=[{"score": 55}],
    )

    ids = {item["id"] for item in payload["suggestions"]}
    assert "learning_gaps" in ids
    assert "practice_gaps" in ids
    learning_gap = next(item for item in payload["suggestions"] if item["id"] == "learning_gaps")
    assert learning_gap["priority"] == "HIGH"
    assert learning_gap["related_lessons"][0]["id"] == "lesson-1"
    assert "测验结果驱动补强" in learning_gap["interview_talking_point"]
