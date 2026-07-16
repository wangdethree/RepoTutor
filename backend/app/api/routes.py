from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile

from app.agents.assessment_agent import AssessmentAgent
from app.agents.curriculum_agent import CurriculumAgent
from app.agents.interview_agent import InterviewAgent
from app.agents.quiz_agent import QuizAgent
from app.agents.qa_agent import QAAgent
from app.agents.remediation_agent import RemediationAgent
from app.agents.teaching_agent import TeachingAgent
from app.core.config import settings
from app.diagrams.architecture_builder import build_all_diagrams
from app.repositories.sqlite_repository import SQLiteRepository
from app.schemas.analysis import from_dict
from app.services.analysis_service import AnalysisService
from app.services.dependency_graph_service import DependencyGraphService
from app.services.github_import_service import GitHubImportError, GitHubImportService
from app.services.lesson_generation_service import LessonGenerationService
from app.services.qa_generation_service import QAGenerationService
from app.services.report_service import ReportService
from app.services.source_browser_service import SourceBrowserService, SourceFileAccessError, SourceFileNotFoundError
from app.services.workflow_service import WorkflowService
from app.utils.safe_zip import ZipSafetyError, safe_extract_zip


router = APIRouter(prefix="/api")
repository = SQLiteRepository()
analysis_service = AnalysisService()
source_browser_service = SourceBrowserService()
report_service = ReportService()
dependency_graph_service = DependencyGraphService()
workflow_service = WorkflowService(repository=repository, analysis_service=analysis_service)
github_import_service = GitHubImportService()
curriculum_agent = CurriculumAgent()
teaching_agent = TeachingAgent()
lesson_generation_service = LessonGenerationService(teaching_agent=teaching_agent, repository=repository)
quiz_agent = QuizAgent()
qa_agent = QAAgent()
qa_generation_service = QAGenerationService(qa_agent=qa_agent, repository=repository)
assessment_agent = AssessmentAgent()
interview_agent = InterviewAgent()
remediation_agent = RemediationAgent()

LLM_SETTING_KEYS = [
    "llm_api_key",
    "llm_base_url",
    "llm_model",
    "llm_temperature",
]

LLM_ENV_NAMES = {
    "llm_api_key": "LLM_API_KEY",
    "llm_base_url": "LLM_BASE_URL",
    "llm_model": "LLM_MODEL",
    "llm_temperature": "LLM_TEMPERATURE",
}


@router.get("/health")
def api_health() -> dict:
    database_status = "ok"
    error = ""
    try:
        repository.list_projects()
    except Exception as exc:
        database_status = "error"
        error = str(exc)
    llm_config = get_llm_settings() if database_status == "ok" else {"api_key_configured": bool(settings.llm_api_key)}
    status = "ok" if database_status == "ok" else "degraded"
    return {
        "status": status,
        "version": "0.1.0",
        "database": database_status,
        "llm_configured": llm_config["api_key_configured"],
        "artifacts_dir": str(settings.artifact_dir),
        "error": error,
    }


@router.get("/capabilities")
def get_capabilities() -> dict:
    llm_config = get_llm_settings()
    return {
        "features": {
            "safe_zip_upload": True,
            "github_url_import": True,
            "static_analysis": True,
            "architecture_diagrams": True,
            "dependency_graph_data": True,
            "langgraph_workflow": True,
            "deterministic_lessons": True,
            "llm_lessons": llm_config["api_key_configured"],
            "llm_project_qa": llm_config["api_key_configured"],
            "llm_audit": True,
            "source_browser": True,
            "learning_progress": True,
            "markdown_reports": True,
            "lesson_markdown_reports": True,
            "review_center": True,
            "quiz_assessment": True,
            "interview_prep": True,
            "remedial_lessons": True,
        },
        "llm": {
            "configured": llm_config["api_key_configured"],
            "model": llm_config["model"],
            "base_url": llm_config["base_url"],
        },
    }


@router.get("/settings/llm")
def get_llm_settings() -> dict:
    stored = repository.get_app_settings(LLM_SETTING_KEYS)
    api_key = stored.get("llm_api_key", settings.llm_api_key)
    base_url = stored.get("llm_base_url", settings.llm_base_url)
    model = stored.get("llm_model", settings.llm_model)
    temperature = stored.get("llm_temperature", str(settings.llm_temperature))
    return {
        "api_key_configured": bool(api_key),
        "api_key_masked": _mask_secret(api_key),
        "api_key_source": _setting_source(stored, "llm_api_key"),
        "base_url": base_url,
        "base_url_source": _setting_source(stored, "llm_base_url"),
        "model": model,
        "model_source": _setting_source(stored, "llm_model"),
        "temperature": float(temperature),
        "temperature_source": _setting_source(stored, "llm_temperature"),
    }


@router.put("/settings/llm")
def update_llm_settings(payload: dict) -> dict:
    current = repository.get_app_settings(LLM_SETTING_KEYS)
    values: dict[str, str] = {}

    base_url = str(payload.get("base_url", current.get("llm_base_url", settings.llm_base_url))).strip()
    model = str(payload.get("model", current.get("llm_model", settings.llm_model))).strip()
    temperature = payload.get("temperature", current.get("llm_temperature", str(settings.llm_temperature)))
    api_key = str(payload.get("api_key", "")).strip()

    if not base_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="模型接口地址必须以 http:// 或 https:// 开头")
    if not model:
        raise HTTPException(status_code=400, detail="模型名称不能为空")
    try:
        normalized_temperature = float(temperature)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="temperature 必须是数字") from exc
    if not 0 <= normalized_temperature <= 2:
        raise HTTPException(status_code=400, detail="temperature 必须在 0 到 2 之间")

    values["llm_base_url"] = base_url.rstrip("/")
    values["llm_model"] = model
    values["llm_temperature"] = str(normalized_temperature)

    if bool(payload.get("clear_api_key")):
        values["llm_api_key"] = ""
    elif api_key and not _looks_masked(api_key):
        values["llm_api_key"] = api_key

    repository.save_app_settings(values)
    return get_llm_settings()


@router.post("/settings/llm/validate")
def validate_llm_settings() -> dict:
    config = get_llm_settings()
    problems: list[str] = []
    if not config["api_key_configured"]:
        problems.append("未配置 API Key，LLM 增强功能会停用")
    if not config["base_url"].startswith(("http://", "https://")):
        problems.append("Base URL 格式不正确")
    if not config["model"]:
        problems.append("模型名称为空")
    return {
        "ok": not problems,
        "mode": "llm_enabled" if not problems else "deterministic_fallback",
        "problems": problems,
        "message": "模型接口配置完整" if not problems else "当前会使用确定性离线规则，不调用模型",
    }


@router.post("/projects/upload")
async def upload_project(
    project_name: str = Form(...),
    python_level: str = Form(...),
    fastapi_level: str = Form(...),
    learning_goal: str = Form(...),
    daily_time: str = Form(...),
    zip_file: UploadFile = File(...),
) -> dict:
    if not zip_file.filename or not zip_file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="仅支持 ZIP 项目文件")

    upload_id = str(uuid.uuid4())
    project_dir = settings.upload_dir / upload_id
    raw_zip = project_dir / "source.zip"
    extract_dir = project_dir / "repo"
    project_dir.mkdir(parents=True, exist_ok=True)

    try:
        with raw_zip.open("wb") as output:
            shutil.copyfileobj(zip_file.file, output)
        safe_extract_zip(raw_zip, extract_dir)
    except ZipSafetyError as exc:
        shutil.rmtree(project_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    profile = {
        "python_level": python_level,
        "fastapi_level": fastapi_level,
        "learning_goal": learning_goal,
        "daily_time": daily_time,
    }
    project = repository.create_project(project_name, zip_file.filename, extract_dir, profile)
    return {"project": project, "profile": profile}


@router.post("/projects/import-github")
def import_github_project(payload: dict) -> dict:
    github_url = str(payload.get("github_url", "")).strip()
    if not github_url:
        raise HTTPException(status_code=400, detail="GitHub 仓库地址不能为空")

    upload_id = str(uuid.uuid4())
    project_dir = settings.upload_dir / upload_id
    raw_zip = project_dir / "github.zip"
    extract_dir = project_dir / "repo"
    project_dir.mkdir(parents=True, exist_ok=True)

    try:
        repo_ref = github_import_service.download_zip(github_url, raw_zip)
        safe_extract_zip(raw_zip, extract_dir)
        repo_root = github_import_service.detect_repo_root(extract_dir)
    except (GitHubImportError, ZipSafetyError) as exc:
        shutil.rmtree(project_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    profile = _profile_from_payload(payload)
    project_name = str(payload.get("project_name") or repo_ref.repo).strip() or repo_ref.repo
    project = repository.create_project(project_name, repo_ref.archive_filename, repo_root, profile)
    return {"project": project, "profile": profile, "github": repo_ref.to_dict()}


@router.get("/projects")
def list_projects() -> dict:
    return {"projects": repository.list_projects()}


@router.get("/projects/{project_id}")
def get_project(project_id: str) -> dict:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"project": project, "profile": repository.get_profile(project_id)}


@router.post("/projects/{project_id}/analyze")
def analyze_project(project_id: str) -> dict:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    analysis = analysis_service.analyze(project_id, Path(project["root_path"]))
    repository.save_analysis(project_id, analysis.to_dict())
    return analysis.to_dict()


@router.get("/projects/{project_id}/analysis")
def get_analysis(project_id: str) -> dict:
    payload = repository.get_analysis(project_id)
    if not payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    return payload


@router.get("/projects/{project_id}/source-files")
def list_source_files(project_id: str) -> dict:
    analysis_payload = repository.get_analysis(project_id)
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    return {"files": source_browser_service.list_files(from_dict(analysis_payload))}


@router.get("/projects/{project_id}/source-files/{file_path:path}")
def get_source_file(project_id: str, file_path: str) -> dict:
    analysis_payload = repository.get_analysis(project_id)
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    try:
        return source_browser_service.read_file(from_dict(analysis_payload), file_path)
    except SourceFileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SourceFileAccessError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/projects/{project_id}/diagrams/generate")
def generate_diagrams(project_id: str) -> dict:
    analysis_payload = repository.get_analysis(project_id)
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    analysis = from_dict(analysis_payload)
    diagrams = [diagram.__dict__ for diagram in build_all_diagrams(analysis)]
    repository.save_diagrams(project_id, diagrams)
    return {"diagrams": diagrams}


@router.get("/projects/{project_id}/diagrams")
def list_diagrams(project_id: str) -> dict:
    diagrams = repository.get_diagrams(project_id)
    return {"diagrams": diagrams}


@router.get("/projects/{project_id}/diagrams/{diagram_id}")
def get_diagram(project_id: str, diagram_id: str) -> dict:
    diagrams = repository.get_diagrams(project_id)
    for diagram in diagrams:
        if diagram["id"] == diagram_id:
            return diagram
    raise HTTPException(status_code=404, detail="图表不存在")


@router.get("/projects/{project_id}/diagrams/{diagram_id}/download")
def download_diagram(project_id: str, diagram_id: str) -> Response:
    diagrams = repository.get_diagrams(project_id)
    for diagram in diagrams:
        if diagram["id"] == diagram_id:
            extension = "mmd" if diagram["format"] == "mermaid" else "puml"
            return Response(
                content=diagram["source"],
                media_type="text/plain; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{diagram_id}.{extension}"'},
            )
    raise HTTPException(status_code=404, detail="图表不存在")


@router.get("/projects/{project_id}/dependency-graph")
def get_dependency_graph(project_id: str) -> dict:
    analysis_payload = repository.get_analysis(project_id)
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    return dependency_graph_service.build(from_dict(analysis_payload))


@router.post("/projects/{project_id}/ask")
async def ask_project(project_id: str, payload: dict[str, str]) -> dict:
    analysis_payload = repository.get_analysis(project_id)
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    question = payload.get("question", "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")
    return await qa_generation_service.answer(from_dict(analysis_payload), question)


@router.post("/projects/{project_id}/agent-runs/onboarding")
def run_onboarding_workflow(project_id: str) -> dict:
    try:
        return workflow_service.run_onboarding(project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/projects/{project_id}/agent-runs")
def list_project_agent_runs(project_id: str) -> dict:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"agent_runs": repository.list_agent_runs(project_id)}


@router.get("/agent-runs/{run_id}")
def get_agent_run(run_id: str) -> dict:
    run = repository.get_agent_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent 运行记录不存在")
    return run


@router.get("/projects/{project_id}/llm-call-logs")
def list_project_llm_call_logs(project_id: str, limit: int = Query(20, ge=1, le=100)) -> dict:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"llm_call_logs": repository.list_llm_call_logs(project_id, limit=limit)}


@router.get("/llm-call-logs/{call_id}")
def get_llm_call_log(call_id: str) -> dict:
    call_log = repository.get_llm_call_log(call_id)
    if not call_log:
        raise HTTPException(status_code=404, detail="LLM 调用记录不存在")
    return call_log


@router.post("/projects/{project_id}/learning-plan")
def generate_learning_plan(project_id: str) -> dict:
    analysis_payload = repository.get_analysis(project_id)
    profile = repository.get_profile(project_id)
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    if not profile:
        raise HTTPException(status_code=404, detail="学习画像不存在")
    analysis = from_dict(analysis_payload)
    plan = curriculum_agent.generate(analysis, profile)
    repository.save_learning_plan(project_id, plan)
    return plan


@router.get("/projects/{project_id}/learning-plan")
def get_learning_plan(project_id: str) -> dict:
    plan = repository.get_learning_plan(project_id)
    if not plan:
        raise HTTPException(status_code=404, detail="请先生成学习路线")
    return plan


@router.get("/projects/{project_id}/progress")
def get_project_progress(project_id: str) -> dict:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    progress = repository.get_learning_progress(project_id)
    if not progress["plan_id"]:
        raise HTTPException(status_code=404, detail="请先生成学习路线")
    return progress


@router.get("/projects/{project_id}/quiz-results")
def list_project_quiz_results(project_id: str) -> dict:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return {"quiz_results": repository.list_quiz_results_for_project(project_id)}


@router.get("/projects/{project_id}/interview-kit")
def get_interview_kit(project_id: str) -> dict:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    analysis_payload = repository.get_analysis(project_id)
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    profile = repository.get_profile(project_id) or {}
    progress = repository.get_learning_progress(project_id)
    return interview_agent.generate(from_dict(analysis_payload), profile, progress)


@router.get("/projects/{project_id}/reports/learning")
def get_learning_report(project_id: str) -> dict:
    return {"markdown": _build_learning_report(project_id)}


@router.get("/projects/{project_id}/reports/learning.md")
def download_learning_report(project_id: str) -> Response:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    filename = _safe_filename(project["name"]) + "-learning-report.md"
    return Response(
        content=_build_learning_report(project_id),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/lessons/{lesson_id}/report.md")
async def download_lesson_report(lesson_id: str) -> Response:
    lesson, project, analysis_payload, quiz = await _build_lesson_report_inputs(lesson_id)
    filename = _safe_filename(f"{project['name']}-{lesson['title']}") + "-lesson-report.md"
    return Response(
        content=report_service.build_lesson_report(
            project=project,
            lesson=lesson,
            analysis=analysis_payload,
            quiz=quiz,
            quiz_results=repository.list_quiz_results_for_lesson(lesson_id),
        ),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/lessons/{lesson_id}")
async def get_lesson(lesson_id: str) -> dict:
    lesson = repository.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="课程不存在")
    project_id = lesson.get("project_id") or _project_id_from_lesson_plan(lesson_id)
    analysis_payload = repository.get_analysis(project_id) if project_id else None
    if analysis_payload and "why" not in lesson:
        lesson = await lesson_generation_service.generate(from_dict(analysis_payload), lesson)
        lesson = _preserve_lesson_progress(repository.get_lesson(lesson_id) or {}, lesson)
        repository.save_lesson_payload(lesson_id, lesson)
    return lesson


@router.post("/lessons/{lesson_id}/generate")
async def generate_lesson(lesson_id: str) -> dict:
    lesson = repository.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="课程不存在")
    project_id = lesson.get("project_id") or _project_id_from_lesson_plan(lesson_id)
    analysis_payload = repository.get_analysis(project_id) if project_id else None
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    lesson_payload = await lesson_generation_service.generate(from_dict(analysis_payload), lesson)
    lesson_payload = _preserve_lesson_progress(lesson, lesson_payload)
    repository.save_lesson_payload(lesson_id, lesson_payload)
    return lesson_payload


@router.post("/lessons/{lesson_id}/status")
def update_lesson_status(lesson_id: str, payload: dict) -> dict:
    status = str(payload.get("status", "")).strip().upper()
    allowed_statuses = {"NOT_STARTED", "IN_PROGRESS", "NEEDS_REVIEW", "COMPLETED"}
    if status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="课程状态不合法")
    lesson = repository.update_lesson_status(lesson_id, status)
    if not lesson:
        raise HTTPException(status_code=404, detail="课程不存在")
    return lesson


@router.post("/lessons/{lesson_id}/complete")
def complete_lesson(lesson_id: str) -> dict:
    lesson = repository.update_lesson_status(lesson_id, "COMPLETED")
    if not lesson:
        raise HTTPException(status_code=404, detail="课程不存在")
    return lesson


@router.get("/lessons/{lesson_id}/quiz-results")
def list_lesson_quiz_results(lesson_id: str) -> dict:
    lesson = repository.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="课程不存在")
    return {"quiz_results": repository.list_quiz_results_for_lesson(lesson_id)}


@router.post("/quiz-results/{result_id}/remediation")
def generate_remediation(result_id: str) -> dict:
    quiz_result = repository.get_quiz_result(result_id)
    if not quiz_result:
        raise HTTPException(status_code=404, detail="测验结果不存在")
    if quiz_result["score"] >= 60:
        raise HTTPException(status_code=400, detail="只有低于 60 分的结果需要生成补充讲解")
    lesson = repository.get_lesson(quiz_result["lesson_id"])
    if not lesson:
        raise HTTPException(status_code=404, detail="课程不存在")
    analysis_payload = repository.get_analysis(quiz_result["project_id"])
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    remediation = remediation_agent.generate(from_dict(analysis_payload), lesson, quiz_result)
    repository.save_quiz(remediation["retry_quiz"])
    return remediation


@router.post("/lessons/{lesson_id}/quiz")
def generate_quiz(lesson_id: str) -> dict:
    lesson = repository.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="课程不存在")
    project_id = lesson.get("project_id") or _project_id_from_lesson_plan(lesson_id)
    analysis_payload = repository.get_analysis(project_id) if project_id else None
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    quiz = quiz_agent.generate(from_dict(analysis_payload), lesson)
    repository.save_quiz(quiz)
    return quiz


@router.post("/quizzes/{quiz_id}/submit")
def submit_quiz(quiz_id: str, answers: dict[str, str]) -> dict:
    quiz = repository.get_quiz(quiz_id)
    if not quiz:
        raise HTTPException(status_code=404, detail="测验不存在")
    evaluation = assessment_agent.evaluate(quiz, answers)
    result = repository.save_quiz_result(quiz_id, evaluation)
    lesson = repository.get_lesson(quiz["lesson_id"]) or {}
    project_id = lesson.get("project_id") or _project_id_from_lesson_plan(quiz["lesson_id"])
    if project_id:
        repository.upsert_mastery(project_id, quiz["lesson_id"], evaluation["score"], evaluation["mastery_level"])
        repository.update_lesson_status(
            quiz["lesson_id"],
            _lesson_status_from_score(evaluation["score"]),
            score=evaluation["score"],
            mastery_level=evaluation["mastery_level"],
        )
    return result


@router.get("/projects/{project_id}/mastery")
def get_mastery(project_id: str) -> dict:
    return {"mastery": repository.get_mastery(project_id)}


def _project_id_from_lesson_plan(lesson_id: str) -> str | None:
    """V1 课程 ID 是 lesson-n，需要通过学习计划反查项目。"""

    for project in repository.list_projects():
        plan = repository.get_learning_plan(project["id"])
        if not plan:
            continue
        if any(lesson["id"] == lesson_id for lesson in plan.get("lessons", [])):
            return project["id"]
    return None


def _profile_from_payload(payload: dict) -> dict[str, str]:
    return {
        "python_level": str(payload.get("python_level", "基础")).strip() or "基础",
        "fastapi_level": str(payload.get("fastapi_level", "了解基础")).strip() or "了解基础",
        "learning_goal": str(payload.get("learning_goal", "看懂项目结构")).strip() or "看懂项目结构",
        "daily_time": str(payload.get("daily_time", "30 分钟")).strip() or "30 分钟",
    }


def _lesson_status_from_score(score: int) -> str:
    if score >= 80:
        return "COMPLETED"
    if score >= 60:
        return "IN_PROGRESS"
    return "NEEDS_REVIEW"


def _preserve_lesson_progress(previous: dict, generated: dict) -> dict:
    for key in ("status", "completed_at", "updated_at", "last_score", "mastery_level"):
        if previous.get(key) is not None:
            generated[key] = previous[key]
    return generated


def _build_learning_report(project_id: str) -> str:
    project = repository.get_project(project_id)
    profile = repository.get_profile(project_id)
    analysis_payload = repository.get_analysis(project_id)
    plan = repository.get_learning_plan(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not profile:
        raise HTTPException(status_code=404, detail="学习画像不存在")
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    if not plan:
        raise HTTPException(status_code=404, detail="请先生成学习路线")
    return report_service.build_learning_report(
        project=project,
        profile=profile,
        analysis=analysis_payload,
        plan=plan,
        progress=repository.get_learning_progress(project_id),
        diagrams=repository.get_diagrams(project_id),
    )


async def _build_lesson_report_inputs(lesson_id: str) -> tuple[dict, dict, dict, dict]:
    lesson = repository.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="课程不存在")

    project_id = lesson.get("project_id") or _project_id_from_lesson_plan(lesson_id)
    if not project_id:
        raise HTTPException(status_code=404, detail="课程所属项目不存在")

    project = repository.get_project(project_id)
    analysis_payload = repository.get_analysis(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")

    if "why" not in lesson:
        lesson = await lesson_generation_service.generate(from_dict(analysis_payload), lesson)
        lesson = _preserve_lesson_progress(repository.get_lesson(lesson_id) or {}, lesson)
        repository.save_lesson_payload(lesson_id, lesson)

    quiz_id = f"quiz-{lesson_id}"
    quiz = repository.get_quiz(quiz_id)
    if not quiz:
        quiz = quiz_agent.generate(from_dict(analysis_payload), lesson)
        repository.save_quiz(quiz)

    return lesson, project, analysis_payload, quiz


def _safe_filename(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value.strip())
    return cleaned.strip("-") or "repotutor"


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def _looks_masked(value: str) -> bool:
    return "*" in value or "..." in value


def _setting_source(stored: dict[str, str], key: str) -> str:
    if key in stored:
        return "database"
    if os.getenv(LLM_ENV_NAMES[key]):
        return "environment"
    return "default"
