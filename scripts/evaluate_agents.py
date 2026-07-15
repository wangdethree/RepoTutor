from __future__ import annotations

import json
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.agents.assessment_agent import AssessmentAgent
from app.agents.curriculum_agent import CurriculumAgent
from app.agents.qa_agent import QAAgent
from app.agents.quiz_agent import QuizAgent
from app.agents.teaching_agent import TeachingAgent
from app.llm.context import LessonCodeContextBuilder
from app.repositories.sqlite_repository import SQLiteRepository
from app.services.analysis_service import AnalysisService
from app.services.call_chain_service import CallChainService
from app.services.workflow_service import WorkflowService


@dataclass
class EvalCase:
    name: str
    status: str
    details: str


def main() -> None:
    """离线 Agent 评测：关注输出质量门槛，不调用外部模型。"""

    cases: list[EvalCase] = []
    repo_root = ROOT / "demo_repositories" / "fastapi_shop"
    analysis = AnalysisService().analyze("demo", repo_root)
    profile = {
        "python_level": "基础",
        "fastapi_level": "了解基础",
        "learning_goal": "看懂项目结构",
        "daily_time": "1 小时",
    }
    plan = CurriculumAgent().generate(analysis, profile)
    lesson = plan["lessons"][0]
    lesson_payload = TeachingAgent().generate(analysis, lesson)

    _record(
        cases,
        "analysis_quality",
        analysis.summary.project_type == "FastAPI 后端服务"
        and analysis.summary.route_count >= 5
        and analysis.summary.model_count >= 3
        and bool(analysis.dependencies),
        f"routes={analysis.summary.route_count} models={analysis.summary.model_count}",
    )
    _record(
        cases,
        "lesson_grounding",
        lesson_payload.get("fact_checked") is True
        and _references_are_valid(analysis, lesson_payload["core_code_locations"])
        and bool(lesson_payload.get("call_chains")),
        (
            f"references={len(lesson_payload['core_code_locations'])} "
            f"call_chains={len(lesson_payload.get('call_chains', []))}"
        ),
    )

    call_chain = CallChainService().build_primary_chain(analysis)
    expected_chain = ["login", "AuthService.login", "UserRepository.get_by_email"]
    _record(
        cases,
        "call_chain_grounding",
        [step["symbol"] for step in call_chain["steps"]] == expected_chain,
        " -> ".join(step["symbol"] for step in call_chain["steps"]),
    )

    snippets = LessonCodeContextBuilder().build(analysis, lesson, lesson_payload)
    _record(
        cases,
        "lesson_code_context",
        bool(snippets) and _snippets_are_valid(analysis, snippets),
        f"snippets={len(snippets)}",
    )

    login_answer = QAAgent().answer(analysis, "登录流程经过哪些函数？")
    _record(
        cases,
        "qa_login_references",
        _answer_has_valid_references(analysis, login_answer)
        and any(reference["file"] == "app/api/auth.py" for reference in login_answer["references"]),
        f"references={len(login_answer['references'])}",
    )

    token_answer = QAAgent().answer(analysis, "JWT token 在哪里处理？")
    _record(
        cases,
        "qa_keyword_references",
        _answer_has_valid_references(analysis, token_answer),
        f"references={len(token_answer['references'])}",
    )

    quiz = QuizAgent().generate(analysis, lesson)
    answers = {
        question["id"]: (
            "main.py app/main.py FastAPI include_router Router Service Repository Database "
            "login AuthService AuthService.login UserRepository get_by_email app/api/auth.py model schema test"
        )
        for question in quiz["questions"]
    }
    result = AssessmentAgent().evaluate(quiz, answers)
    _record(cases, "quiz_assessment_gate", result["score"] >= 80, f"score={result['score']}")

    _evaluate_workflow_trace(cases, repo_root, profile)

    report = {
        "passed": sum(1 for case in cases if case.status == "PASSED"),
        "failed": sum(1 for case in cases if case.status == "FAILED"),
        "skipped": sum(1 for case in cases if case.status == "SKIPPED"),
        "cases": [asdict(case) for case in cases],
    }
    report_path = ROOT / "artifacts" / "reports" / "agent_eval.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if report["failed"]:
        print("agent evaluation failed")
        for case in cases:
            if case.status == "FAILED":
                print(f"- {case.name}: {case.details}")
        print(f"report={report_path}")
        raise SystemExit(1)

    print("agent evaluation passed")
    print(f"passed={report['passed']} failed={report['failed']} skipped={report['skipped']}")
    print(f"report={report_path}")


def _record(cases: list[EvalCase], name: str, passed: bool, details: str) -> None:
    cases.append(EvalCase(name=name, status="PASSED" if passed else "FAILED", details=details))


def _skip(cases: list[EvalCase], name: str, details: str) -> None:
    cases.append(EvalCase(name=name, status="SKIPPED", details=details))


def _evaluate_workflow_trace(cases: list[EvalCase], repo_root: Path, profile: dict) -> None:
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = SQLiteRepository(f"sqlite:///{Path(temp_dir) / 'agent-eval.db'}")
            project = repository.create_project("FastAPI Shop", "fastapi_shop.zip", repo_root, profile)
            run = WorkflowService(repository=repository).run_onboarding(project["id"])
            _record(
                cases,
                "workflow_trace",
                run["status"] == "SUCCEEDED"
                and len(run["events"]) == 4
                and repository.get_learning_plan(project["id"]) is not None,
                f"status={run['status']} events={len(run['events'])}",
            )
    except ModuleNotFoundError as exc:
        if exc.name != "langgraph":
            raise
        _skip(cases, "workflow_trace", "langgraph dependency is not installed")


def _references_are_valid(analysis, references: list[dict]) -> bool:
    files = {file.path: file for file in analysis.files}
    return all(
        reference.get("file") in files and 1 <= int(reference.get("line") or 0) <= files[reference["file"]].line_count
        for reference in references
    )


def _snippets_are_valid(analysis, snippets: list[dict]) -> bool:
    files = {file.path: file for file in analysis.files}
    return all(
        snippet.get("file") in files
        and 1 <= int(snippet.get("start_line") or 0) <= int(snippet.get("end_line") or 0) <= files[snippet["file"]].line_count
        and bool(snippet.get("code"))
        for snippet in snippets
    )


def _answer_has_valid_references(analysis, answer: dict) -> bool:
    references = answer.get("references", [])
    return bool(references) and _references_are_valid(analysis, references)


if __name__ == "__main__":
    main()
