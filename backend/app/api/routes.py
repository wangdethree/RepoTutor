from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.agents.assessment_agent import AssessmentAgent
from app.agents.curriculum_agent import CurriculumAgent
from app.agents.quiz_agent import QuizAgent
from app.agents.teaching_agent import TeachingAgent
from app.core.config import settings
from app.diagrams.architecture_builder import build_all_diagrams
from app.repositories.sqlite_repository import SQLiteRepository
from app.schemas.analysis import from_dict
from app.services.analysis_service import AnalysisService
from app.utils.safe_zip import ZipSafetyError, safe_extract_zip


router = APIRouter(prefix="/api")
repository = SQLiteRepository()
analysis_service = AnalysisService()
curriculum_agent = CurriculumAgent()
teaching_agent = TeachingAgent()
quiz_agent = QuizAgent()
assessment_agent = AssessmentAgent()


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


@router.get("/lessons/{lesson_id}")
def get_lesson(lesson_id: str) -> dict:
    lesson = repository.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="课程不存在")
    project_id = lesson.get("project_id") or _project_id_from_lesson_plan(lesson_id)
    analysis_payload = repository.get_analysis(project_id) if project_id else None
    if analysis_payload and "why" not in lesson:
        lesson = teaching_agent.generate(from_dict(analysis_payload), lesson)
        repository.save_lesson_payload(lesson_id, lesson)
    return lesson


@router.post("/lessons/{lesson_id}/generate")
def generate_lesson(lesson_id: str) -> dict:
    lesson = repository.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="课程不存在")
    project_id = _project_id_from_lesson_plan(lesson_id)
    analysis_payload = repository.get_analysis(project_id) if project_id else None
    if not analysis_payload:
        raise HTTPException(status_code=404, detail="请先分析项目")
    lesson_payload = teaching_agent.generate(from_dict(analysis_payload), lesson)
    repository.save_lesson_payload(lesson_id, lesson_payload)
    return lesson_payload


@router.post("/lessons/{lesson_id}/quiz")
def generate_quiz(lesson_id: str) -> dict:
    lesson = repository.get_lesson(lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="课程不存在")
    project_id = _project_id_from_lesson_plan(lesson_id)
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
    project_id = _project_id_from_lesson_plan(quiz["lesson_id"])
    if project_id:
        repository.upsert_mastery(project_id, quiz["lesson_id"], evaluation["score"], evaluation["mastery_level"])
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

