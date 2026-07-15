from __future__ import annotations

from pathlib import Path

from app.repositories.sqlite_repository import SQLiteRepository
from app.services.workflow_service import WorkflowService


def test_onboarding_workflow_creates_trace_and_artifacts(tmp_path: Path) -> None:
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'workflow.db'}")
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    project = repository.create_project(
        name="FastAPI Shop",
        original_filename="fastapi_shop.zip",
        root_path=repo_root,
        profile={
            "python_level": "基础",
            "fastapi_level": "了解基础",
            "learning_goal": "看懂项目结构",
            "daily_time": "1 小时",
        },
    )

    run = WorkflowService(repository=repository).run_onboarding(project["id"])

    assert run["status"] == "SUCCEEDED"
    assert run["run_type"] == "repository_onboarding"
    assert run["state"]["next_action"] == "READY_FOR_FIRST_LESSON"
    assert run["state"]["current_lesson_id"]
    assert repository.get_analysis(project["id"]) is not None
    assert len(repository.get_diagrams(project["id"])) >= 4
    assert repository.get_learning_plan(project["id"])["total_lessons"] >= 7
    assert [event["step_name"] for event in run["events"]] == [
        "analyze_repository",
        "generate_architecture_views",
        "load_learner_profile",
        "generate_curriculum",
    ]


def test_onboarding_workflow_supports_multiple_projects(tmp_path: Path) -> None:
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'workflow.db'}")
    repo_root = Path(__file__).resolve().parents[2] / "demo_repositories" / "fastapi_shop"
    profile = {
        "python_level": "基础",
        "fastapi_level": "了解基础",
        "learning_goal": "看懂项目结构",
        "daily_time": "1 小时",
    }
    first = repository.create_project("FastAPI Shop A", "a.zip", repo_root, profile)
    second = repository.create_project("FastAPI Shop B", "b.zip", repo_root, profile)
    workflow = WorkflowService(repository=repository)

    first_run = workflow.run_onboarding(first["id"])
    second_run = workflow.run_onboarding(second["id"])

    assert first_run["status"] == "SUCCEEDED"
    assert second_run["status"] == "SUCCEEDED"
    assert {diagram["id"] for diagram in repository.get_diagrams(first["id"])} == {
        diagram["id"] for diagram in repository.get_diagrams(second["id"])
    }
