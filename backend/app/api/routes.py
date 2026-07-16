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
from app.services.demo_readiness_service import DemoReadinessService
from app.services.demo_script_service import DemoScriptService
from app.services.dependency_graph_service import DependencyGraphService
from app.services.diff_impact_service import DiffImpactService
from app.services.github_import_service import GitHubImportError, GitHubImportService
from app.services.incremental_learning_service import IncrementalLearningService
from app.services.interview_readiness_service import InterviewReadinessService
from app.services.knowledge_card_service import KnowledgeCardService
from app.services.lesson_generation_service import LessonGenerationService
from app.services.profile_service import build_profile, build_profile_from_payload
from app.services.practice_task_service import PracticeTaskService
from app.services.pr_review_service import PRReviewService
from app.services.project_dashboard_service import ProjectDashboardService
from app.services.project_improvement_service import ProjectImprovementService
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
demo_readiness_service = DemoReadinessService()
demo_script_service = DemoScriptService()
dependency_graph_service = DependencyGraphService()
diff_impact_service = DiffImpactService()
knowledge_card_service = KnowledgeCardService()
practice_task_service = PracticeTaskService()
pr_review_service = PRReviewService()
project_dashboard_service = ProjectDashboardService()
project_improvement_service = ProjectImprovementService()
interview_readiness_service = InterviewReadinessService()
workflow_service = WorkflowService(repository=repository, analysis_service=analysis_service)
github_import_service = GitHubImportService()
incremental_learning_service = IncrementalLearningService()
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
            "built_in_demo_project": True,
            "static_analysis": True,
            "architecture_diagrams": True,
            "dependency_graph_data": True,
            "diff_impact_analysis": True,
            "pr_review_pack": True,
            "pr_review_markdown_export": True,
            "incremental_learning": True,
            "incremental_learning_markdown_export": True,
            "demo_readiness": True,
            "demo_script": True,
            "demo_script_markdown_export": True,
            "improvement_suggestions": True,
            "improvement_report_export": True,
            "langgraph_workflow": True,
            "deterministic_lessons": True,
            "llm_lessons": llm_config["api_key_configured"],
            "llm_project_qa": llm_config["api_key_configured"],
            "llm_audit": True,
            "source_browser": True,
            "source_browser_return_to_lesson": True,
            "learning_progress": True,
            "markdown_reports": True,
            "lesson_markdown_reports": True,
            "lesson_report_practice_tasks": True,
            "report_page_lesson_download": True,
            "review_center": True,
            "quiz_assessment": True,
            "interview_prep": True,
            "interview_markdown_export": True,
            "interview_readiness": True,
            "interview_question_records": True,
            "remedial_lessons": True,
            "knowledge_cards": True,
            "practice_tasks": True,
            "practice_task_source_links": True,
            "practice_progress": True,
            "project_dashboard": True,
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
    learning_goal: str = Form("看懂项目结构"),
    learning_goals: str = Form(""),
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

    profile = build_profile(python_level, fastapi_level, learning_goal, daily_time, learning_goals)
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


@router.post("/demo-projects/fastapi-shop")
def bootstrap_fastapi_shop_demo(payload: dict | None = None) -> dict:
    demo_root = _fastapi_shop_demo_root()
    if not demo_root.exists():
        raise HTTPException(status_code=404, detail="内置示例项目不存在")
    profile = _demo_profile(payload or {})
    project = _find_demo_project(demo_root)
    created = False
    if not project:
        project = repository.create_project("FastAPI Shop Demo", "fastapi_shop_demo", demo_root, profile)
        created = True
    analysis_payload = _ensure_project_analysis(project["id"], demo_root)
    diagrams = _ensure_project_diagrams(project["id"], analysis_payload)
    plan = _ensure_project_learning_plan(project["id"], analysis_payload, repository.get_profile(project["id"]) or profile)
    return {
        "project": repository.get_project(project["id"]),
        "profile": repository.get_profile(project["id"]),
        "demo": {
            "created": created,
            "source": "demo_repositories/fastapi_shop",
            "analysis_ready": True,
            "diagrams": len(diagrams),
            "lessons": plan.get("total_lessons", len(plan.get("lessons", []))),
        },
    }


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


@router.post("/projects/{project_id}/diff-impact")
def analyze_diff_impact(project_id: str, payload: dict) -> dict:
    diff_text = str(payload.get("diff", "")).strip()
    if not diff_text:
        raise HTTPException(status_code=400, detail="diff 内容不能为空")
    return _build_diff_impact(project_id, diff_text)


@router.post("/projects/{project_id}/pr-review")
def build_pr_review(project_id: str, payload: dict) -> dict:
    diff_text = str(payload.get("diff", "")).strip()
    if not diff_text:
        raise HTTPException(status_code=400, detail="diff 内容不能为空")
    return _build_pr_review(project_id, diff_text)


@router.post("/projects/{project_id}/pr-review.md")
def download_pr_review(project_id: str, payload: dict) -> Response:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    diff_text = str(payload.get("diff", "")).strip()
    if not diff_text:
        raise HTTPException(status_code=400, detail="diff 内容不能为空")
    filename = _safe_filename(project["name"]) + "-pr-review.md"
    return Response(
        content=report_service.build_pr_review_report(project, _build_pr_review(project_id, diff_text)),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/projects/{project_id}/incremental-learning")
def build_incremental_learning(project_id: str, payload: dict) -> dict:
    diff_text = str(payload.get("diff", "")).strip()
    if not diff_text:
        raise HTTPException(status_code=400, detail="diff 内容不能为空")
    return _build_incremental_learning(project_id, diff_text)


@router.post("/projects/{project_id}/incremental-learning.md")
def download_incremental_learning(project_id: str, payload: dict) -> Response:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    diff_text = str(payload.get("diff", "")).strip()
    if not diff_text:
        raise HTTPException(status_code=400, detail="diff 内容不能为空")
    filename = _safe_filename(project["name"]) + "-incremental-learning.md"
    markdown = report_service.build_incremental_learning_report(
        project,
        _build_incremental_learning(project_id, diff_text),
    )
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


@router.get("/projects/{project_id}/dashboard")
def get_project_dashboard(project_id: str) -> dict:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    analysis_payload = repository.get_analysis(project_id)
    plan = repository.get_learning_plan(project_id)
    progress = repository.get_learning_progress(project_id)
    diagrams = repository.get_diagrams(project_id) if analysis_payload else []
    quiz_results = repository.list_quiz_results_for_project(project_id) if plan else []
    practice_progress = _optional_project_practice_progress(project_id, analysis_payload, plan)
    interview_readiness = _optional_interview_readiness(project_id, analysis_payload, plan, progress)
    demo_readiness = demo_readiness_service.build(
        project=project,
        analysis=analysis_payload,
        plan=plan,
        diagrams=diagrams,
        progress=progress,
        practice_progress=practice_progress,
        quiz_results=quiz_results,
        interview_readiness=interview_readiness,
    )
    improvement_suggestions = (
        project_improvement_service.build(
            project=project,
            analysis=analysis_payload,
            plan=plan,
            progress=progress,
            practice_progress=practice_progress,
            quiz_results=quiz_results,
        )
        if analysis_payload
        else {"priority_counts": {"HIGH": 0, "MEDIUM": 0, "LOW": 0}, "next_actions": [], "suggestions": []}
    )
    return project_dashboard_service.build(
        project=project,
        analysis=analysis_payload,
        plan=plan,
        progress=progress,
        practice_progress=practice_progress,
        interview_readiness=interview_readiness,
        demo_readiness=demo_readiness,
        improvement_suggestions=improvement_suggestions,
    )


@router.get("/projects/{project_id}/demo-readiness")
def get_project_demo_readiness(project_id: str) -> dict:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    analysis_payload = repository.get_analysis(project_id)
    plan = repository.get_learning_plan(project_id)
    progress = repository.get_learning_progress(project_id)
    diagrams = repository.get_diagrams(project_id) if analysis_payload else []
    quiz_results = repository.list_quiz_results_for_project(project_id) if plan else []
    practice_progress = _optional_project_practice_progress(project_id, analysis_payload, plan)
    interview_readiness = _optional_interview_readiness(project_id, analysis_payload, plan, progress)
    return demo_readiness_service.build(
        project=project,
        analysis=analysis_payload,
        plan=plan,
        diagrams=diagrams,
        progress=progress,
        practice_progress=practice_progress,
        quiz_results=quiz_results,
        interview_readiness=interview_readiness,
    )


@router.get("/projects/{project_id}/demo-script")
def get_project_demo_script(project_id: str) -> dict:
    return _build_project_demo_script(project_id)


@router.get("/projects/{project_id}/demo-script.md")
def download_project_demo_script(project_id: str) -> Response:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    filename = _safe_filename(project["name"]) + "-demo-script.md"
    return Response(
        content=report_service.build_demo_script_report(project, _build_project_demo_script(project_id)),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/projects/{project_id}/improvement-suggestions")
def get_project_improvement_suggestions(project_id: str) -> dict:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    analysis_payload = repository.get_analysis(project_id)
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    plan = repository.get_learning_plan(project_id)
    progress = repository.get_learning_progress(project_id)
    practice_progress = _optional_project_practice_progress(project_id, analysis_payload, plan)
    quiz_results = repository.list_quiz_results_for_project(project_id) if plan else []
    return project_improvement_service.build(
        project=project,
        analysis=analysis_payload,
        plan=plan,
        progress=progress,
        practice_progress=practice_progress,
        quiz_results=quiz_results,
    )


@router.get("/projects/{project_id}/practice-progress")
def get_project_practice_progress(project_id: str) -> dict:
    return _build_project_practice_progress(project_id)


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
    return _interview_kit_with_records(
        project_id,
        interview_agent.generate(from_dict(analysis_payload), profile, progress),
    )


@router.get("/projects/{project_id}/interview-kit.md")
def download_interview_kit(project_id: str) -> Response:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    filename = _safe_filename(project["name"]) + "-interview-kit.md"
    return Response(
        content=_build_interview_report(project_id),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/projects/{project_id}/interview-readiness")
def get_interview_readiness(project_id: str) -> dict:
    project = repository.get_project(project_id)
    analysis_payload = repository.get_analysis(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    progress = repository.get_learning_progress(project_id)
    if not progress["plan_id"]:
        raise HTTPException(status_code=404, detail="请先生成学习路线")
    profile = repository.get_profile(project_id) or {}
    interview_kit = _interview_kit_with_records(
        project_id,
        interview_agent.generate(from_dict(analysis_payload), profile, progress),
    )
    return interview_readiness_service.build(
        progress=progress,
        practice_progress=_build_project_practice_progress(project_id),
        quiz_results=repository.list_quiz_results_for_project(project_id),
        interview_kit=interview_kit,
    )


@router.post("/projects/{project_id}/interview-questions/{question_id}/status")
def update_interview_question_status(project_id: str, question_id: str, payload: dict) -> dict:
    project = repository.get_project(project_id)
    analysis_payload = repository.get_analysis(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    profile = repository.get_profile(project_id) or {}
    progress = repository.get_learning_progress(project_id)
    interview_kit = interview_agent.generate(from_dict(analysis_payload), profile, progress)
    if not any(question["id"] == question_id for question in interview_kit.get("questions", [])):
        raise HTTPException(status_code=404, detail="面试题不存在")
    repository.upsert_interview_question_record(project_id, question_id, bool(payload.get("mastered")))
    return _interview_kit_with_records(project_id, interview_kit)


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
            practice_tasks=_practice_tasks_with_records(
                lesson_id,
                practice_task_service.build(lesson, quiz),
            ),
        ),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/lessons/{lesson_id}/knowledge-cards")
async def get_lesson_knowledge_cards(lesson_id: str) -> dict:
    lesson, _project, _analysis_payload, quiz = await _build_lesson_report_inputs(lesson_id)
    return knowledge_card_service.build(lesson, quiz)


@router.get("/lessons/{lesson_id}/practice-tasks")
async def get_lesson_practice_tasks(lesson_id: str) -> dict:
    lesson, _project, _analysis_payload, quiz = await _build_lesson_report_inputs(lesson_id)
    return _practice_tasks_with_records(lesson_id, practice_task_service.build(lesson, quiz))


@router.post("/lessons/{lesson_id}/practice-tasks/{task_id}/status")
async def update_practice_task_status(lesson_id: str, task_id: str, payload: dict) -> dict:
    lesson, _project, _analysis_payload, quiz = await _build_lesson_report_inputs(lesson_id)
    tasks_payload = practice_task_service.build(lesson, quiz)
    if not any(task["id"] == task_id for task in tasks_payload["tasks"]):
        raise HTTPException(status_code=404, detail="动手任务不存在")
    repository.upsert_practice_task_record(lesson_id, task_id, bool(payload.get("completed")))
    return _practice_tasks_with_records(lesson_id, tasks_payload)


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


def _profile_from_payload(payload: dict) -> dict:
    return build_profile_from_payload(payload)


def _demo_profile(payload: dict) -> dict:
    return build_profile_from_payload(
        {
            "python_level": payload.get("python_level", "基础"),
            "fastapi_level": payload.get("fastapi_level", "了解基础"),
            "learning_goal": payload.get("learning_goal", "看懂项目结构、准备项目面试"),
            "learning_goals": payload.get("learning_goals", ["看懂项目结构", "准备项目面试"]),
            "daily_time": payload.get("daily_time", "1 小时"),
        }
    )


def _fastapi_shop_demo_root() -> Path:
    return Path(__file__).resolve().parents[3] / "demo_repositories" / "fastapi_shop"


def _find_demo_project(demo_root: Path) -> dict | None:
    target = str(demo_root.resolve())
    for project in repository.list_projects():
        if project.get("original_filename") != "fastapi_shop_demo":
            continue
        try:
            if str(Path(project["root_path"]).resolve()) == target:
                return project
        except OSError:
            continue
    return None


def _ensure_project_analysis(project_id: str, root_path: Path) -> dict:
    analysis_payload = repository.get_analysis(project_id)
    if analysis_payload:
        return analysis_payload
    analysis = analysis_service.analyze(project_id, root_path)
    repository.save_analysis(project_id, analysis.to_dict())
    return analysis.to_dict()


def _ensure_project_diagrams(project_id: str, analysis_payload: dict) -> list[dict]:
    diagrams = repository.get_diagrams(project_id)
    if diagrams:
        return diagrams
    diagrams = [diagram.__dict__ for diagram in build_all_diagrams(from_dict(analysis_payload))]
    repository.save_diagrams(project_id, diagrams)
    return repository.get_diagrams(project_id)


def _ensure_project_learning_plan(project_id: str, analysis_payload: dict, profile: dict) -> dict:
    plan = repository.get_learning_plan(project_id)
    if plan:
        return plan
    plan = curriculum_agent.generate(from_dict(analysis_payload), profile)
    repository.save_learning_plan(project_id, plan)
    return repository.get_learning_plan(project_id) or plan


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
    progress = repository.get_learning_progress(project_id)
    practice_progress = _build_project_practice_progress(project_id)
    improvement_suggestions = project_improvement_service.build(
        project=project,
        analysis=analysis_payload,
        plan=plan,
        progress=progress,
        practice_progress=practice_progress,
        quiz_results=repository.list_quiz_results_for_project(project_id),
    )
    return report_service.build_learning_report(
        project=project,
        profile=profile,
        analysis=analysis_payload,
        plan=plan,
        progress=progress,
        diagrams=repository.get_diagrams(project_id),
        practice_progress=practice_progress,
        improvement_suggestions=improvement_suggestions,
    )


def _build_interview_report(project_id: str) -> str:
    project = repository.get_project(project_id)
    analysis_payload = repository.get_analysis(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    profile = repository.get_profile(project_id) or {}
    progress = repository.get_learning_progress(project_id)
    kit = _interview_kit_with_records(
        project_id,
        interview_agent.generate(from_dict(analysis_payload), profile, progress),
    )
    plan = repository.get_learning_plan(project_id)
    quiz_results = repository.list_quiz_results_for_project(project_id) if plan else []
    practice_progress = _build_project_practice_progress(project_id) if plan else None
    readiness = None
    if progress["plan_id"]:
        readiness = interview_readiness_service.build(
            progress=progress,
            practice_progress=practice_progress,
            quiz_results=quiz_results,
            interview_kit=kit,
        )
    improvement_suggestions = project_improvement_service.build(
        project=project,
        analysis=analysis_payload,
        plan=plan,
        progress=progress,
        practice_progress=practice_progress,
        quiz_results=quiz_results,
    )
    return report_service.build_interview_report(
        project=project,
        kit=kit,
        readiness=readiness,
        improvement_suggestions=improvement_suggestions,
    )


def _build_project_demo_script(project_id: str) -> dict:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    analysis_payload = repository.get_analysis(project_id)
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    plan = repository.get_learning_plan(project_id)
    progress = repository.get_learning_progress(project_id)
    diagrams = repository.get_diagrams(project_id)
    quiz_results = repository.list_quiz_results_for_project(project_id) if plan else []
    practice_progress = _optional_project_practice_progress(project_id, analysis_payload, plan)
    interview_readiness = _optional_interview_readiness(project_id, analysis_payload, plan, progress)
    demo_readiness = demo_readiness_service.build(
        project=project,
        analysis=analysis_payload,
        plan=plan,
        diagrams=diagrams,
        progress=progress,
        practice_progress=practice_progress,
        quiz_results=quiz_results,
        interview_readiness=interview_readiness,
    )
    improvement_suggestions = project_improvement_service.build(
        project=project,
        analysis=analysis_payload,
        plan=plan,
        progress=progress,
        practice_progress=practice_progress,
        quiz_results=quiz_results,
    )
    return demo_script_service.build(
        project=project,
        analysis=analysis_payload,
        plan=plan,
        progress=progress,
        demo_readiness=demo_readiness,
        improvement_suggestions=improvement_suggestions,
    )


def _build_pr_review(project_id: str, diff_text: str) -> dict:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return pr_review_service.build(project, diff_text, _build_diff_impact(project_id, diff_text))


def _build_incremental_learning(project_id: str, diff_text: str) -> dict:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    impact = _build_diff_impact(project_id, diff_text)
    pr_review = pr_review_service.build(project, diff_text, impact)
    return incremental_learning_service.build(project, impact, pr_review)


def _build_diff_impact(project_id: str, diff_text: str) -> dict:
    analysis_payload = repository.get_analysis(project_id)
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    return diff_impact_service.analyze(
        from_dict(analysis_payload),
        diff_text,
        plan=repository.get_learning_plan(project_id),
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


def _practice_tasks_with_records(lesson_id: str, tasks_payload: dict) -> dict:
    records = {record["task_id"]: record for record in repository.list_practice_task_records(lesson_id)}
    completed_count = 0
    for task in tasks_payload["tasks"]:
        record = records.get(task["id"], {})
        task["completed"] = bool(record.get("completed", False))
        task["completed_at"] = record.get("completed_at", "")
        task["updated_at"] = record.get("updated_at", "")
        if task["completed"]:
            completed_count += 1
    tasks_payload["completed_task_count"] = completed_count
    tasks_payload["completion_rate"] = round(completed_count / tasks_payload["task_count"] * 100) if tasks_payload["task_count"] else 0
    return tasks_payload


def _interview_kit_with_records(project_id: str, kit: dict) -> dict:
    records = {
        record["question_id"]: record
        for record in repository.list_interview_question_records(project_id)
    }
    mastered_count = 0
    for question in kit.get("questions", []):
        record = records.get(question["id"], {})
        question["mastered"] = bool(record.get("mastered", False))
        question["mastered_at"] = record.get("mastered_at", "")
        question["updated_at"] = record.get("updated_at", "")
        if question["mastered"]:
            mastered_count += 1
    question_count = len(kit.get("questions", []))
    kit["mastered_question_count"] = mastered_count
    kit["question_mastery_rate"] = round(mastered_count / question_count * 100) if question_count else 0
    return kit


def _optional_project_practice_progress(project_id: str, analysis_payload: dict | None, plan: dict | None) -> dict | None:
    if not analysis_payload or not plan:
        return None
    return _build_project_practice_progress(project_id)


def _optional_interview_readiness(
    project_id: str,
    analysis_payload: dict | None,
    plan: dict | None,
    progress: dict,
) -> dict | None:
    if not analysis_payload or not plan:
        return None
    profile = repository.get_profile(project_id) or {}
    interview_kit = _interview_kit_with_records(
        project_id,
        interview_agent.generate(from_dict(analysis_payload), profile, progress),
    )
    return interview_readiness_service.build(
        progress=progress,
        practice_progress=_build_project_practice_progress(project_id),
        quiz_results=repository.list_quiz_results_for_project(project_id),
        interview_kit=interview_kit,
    )


def _build_project_practice_progress(project_id: str) -> dict:
    project = repository.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    analysis_payload = repository.get_analysis(project_id)
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    plan = repository.get_learning_plan(project_id)
    if not plan:
        raise HTTPException(status_code=404, detail="请先生成学习路线")

    analysis = from_dict(analysis_payload)
    lesson_items = []
    total_tasks = 0
    completed_tasks = 0
    total_estimated_minutes = 0

    for lesson in plan.get("lessons", []):
        lesson_payload = (
            lesson
            if lesson.get("core_code_locations")
            else teaching_agent.generate(analysis, lesson)
        )
        lesson_payload = _preserve_lesson_progress(lesson, lesson_payload)
        quiz = repository.get_quiz(f"quiz-{lesson['id']}") or quiz_agent.generate(analysis, lesson_payload)
        tasks_payload = _practice_tasks_with_records(
            lesson["id"],
            practice_task_service.build(lesson_payload, quiz),
        )
        lesson_estimated_minutes = sum(task.get("estimated_minutes", 0) for task in tasks_payload["tasks"])

        total_tasks += tasks_payload["task_count"]
        completed_tasks += tasks_payload["completed_task_count"]
        total_estimated_minutes += lesson_estimated_minutes
        lesson_items.append(
            {
                "lesson_id": lesson["id"],
                "lesson_title": lesson["title"],
                "order_index": lesson["order_index"],
                "status": lesson.get("status", "NOT_STARTED"),
                "task_count": tasks_payload["task_count"],
                "completed_task_count": tasks_payload["completed_task_count"],
                "completion_rate": tasks_payload["completion_rate"],
                "estimated_minutes": lesson_estimated_minutes,
                "pending_tasks": [
                    task["title"]
                    for task in tasks_payload["tasks"]
                    if not task.get("completed")
                ],
            }
        )

    next_practice_lesson = next(
        (lesson for lesson in lesson_items if lesson["completed_task_count"] < lesson["task_count"]),
        None,
    )
    return {
        "project_id": project_id,
        "total_lessons": len(lesson_items),
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "remaining_tasks": total_tasks - completed_tasks,
        "completion_rate": round(completed_tasks / total_tasks * 100) if total_tasks else 0,
        "total_estimated_minutes": total_estimated_minutes,
        "next_practice_lesson_id": next_practice_lesson["lesson_id"] if next_practice_lesson else "",
        "lessons": lesson_items,
    }


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
