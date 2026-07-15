from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.curriculum_agent import CurriculumAgent
from app.diagrams.architecture_builder import build_all_diagrams
from app.graphs.learning_graph import RepoTutorState, build_onboarding_graph
from app.repositories.sqlite_repository import SQLiteRepository
from app.schemas.analysis import from_dict
from app.services.analysis_service import AnalysisService


class WorkflowService:
    """RepoTutor 的 Agent 工作流编排服务。"""

    def __init__(
        self,
        repository: SQLiteRepository,
        analysis_service: AnalysisService | None = None,
        curriculum_agent: CurriculumAgent | None = None,
    ) -> None:
        self.repository = repository
        self.analysis_service = analysis_service or AnalysisService()
        self.curriculum_agent = curriculum_agent or CurriculumAgent()
        self.graph = build_onboarding_graph(
            {
                "analyze_repository": self._analyze_repository,
                "generate_architecture_views": self._generate_architecture_views,
                "load_learner_profile": self._load_learner_profile,
                "generate_curriculum": self._generate_curriculum,
            }
        )

    def run_onboarding(self, project_id: str) -> dict:
        project = self.repository.get_project(project_id)
        if not project:
            raise ValueError("项目不存在")

        initial_state: RepoTutorState = {
            "project_id": project_id,
            "root_path": project["root_path"],
            "next_action": "START",
        }
        run = self.repository.create_agent_run(project_id, "repository_onboarding", dict(initial_state))
        state: RepoTutorState = {**initial_state, "run_id": run["id"]}

        try:
            final_state = self.graph.invoke(state)
            self.repository.finish_agent_run(run["id"], "SUCCEEDED", dict(final_state))
            return self.repository.get_agent_run(run["id"]) or {}
        except Exception as exc:
            failed_state = dict(state)
            failed_state["next_action"] = "FAILED"
            self.repository.record_agent_event(
                run["id"],
                "workflow",
                "FAILED",
                {"error": str(exc)},
            )
            self.repository.finish_agent_run(run["id"], "FAILED", failed_state, str(exc))
            raise

    def _analyze_repository(self, state: RepoTutorState) -> dict[str, Any]:
        run_id = state["run_id"]
        project_id = state["project_id"]
        analysis = self.analysis_service.analyze(project_id, Path(state["root_path"]))
        payload = analysis.to_dict()
        self.repository.save_analysis(project_id, payload)
        self.repository.record_agent_event(
            run_id,
            "analyze_repository",
            "SUCCEEDED",
            {
                "file_count": payload["summary"]["file_count"],
                "route_count": payload["summary"]["route_count"],
                "model_count": payload["summary"]["model_count"],
            },
        )
        return {
            "analysis": payload,
            "repository_summary": payload["summary"],
            "next_action": "GENERATE_ARCHITECTURE_VIEWS",
        }

    def _generate_architecture_views(self, state: RepoTutorState) -> dict[str, Any]:
        run_id = state["run_id"]
        project_id = state["project_id"]
        analysis = from_dict(state["analysis"])
        diagrams = [diagram.__dict__ for diagram in build_all_diagrams(analysis)]
        self.repository.save_diagrams(project_id, diagrams)
        self.repository.record_agent_event(
            run_id,
            "generate_architecture_views",
            "SUCCEEDED",
            {"diagram_count": len(diagrams), "diagram_ids": [diagram["id"] for diagram in diagrams]},
        )
        return {
            "architecture_views": diagrams,
            "next_action": "LOAD_LEARNER_PROFILE",
        }

    def _load_learner_profile(self, state: RepoTutorState) -> dict[str, Any]:
        run_id = state["run_id"]
        project_id = state["project_id"]
        profile = self.repository.get_profile(project_id)
        if not profile:
            raise ValueError("学习画像不存在")
        self.repository.record_agent_event(
            run_id,
            "load_learner_profile",
            "SUCCEEDED",
            {
                "python_level": profile["python_level"],
                "fastapi_level": profile["fastapi_level"],
                "learning_goal": profile["learning_goal"],
                "daily_time": profile["daily_time"],
            },
        )
        return {
            "learner_profile": profile,
            "next_action": "GENERATE_CURRICULUM",
        }

    def _generate_curriculum(self, state: RepoTutorState) -> dict[str, Any]:
        run_id = state["run_id"]
        project_id = state["project_id"]
        analysis = from_dict(state["analysis"])
        plan = self.curriculum_agent.generate(analysis, state["learner_profile"])
        self.repository.save_learning_plan(project_id, plan)
        current_lesson_id = plan["lessons"][0]["id"] if plan.get("lessons") else None
        self.repository.record_agent_event(
            run_id,
            "generate_curriculum",
            "SUCCEEDED",
            {
                "plan_id": plan["id"],
                "total_lessons": plan["total_lessons"],
                "current_lesson_id": current_lesson_id,
            },
        )
        return {
            "learning_plan": plan,
            "current_lesson_id": current_lesson_id,
            "next_action": "READY_FOR_FIRST_LESSON",
        }

