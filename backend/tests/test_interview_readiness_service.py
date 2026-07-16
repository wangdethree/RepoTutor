from __future__ import annotations

from app.services.interview_readiness_service import InterviewReadinessService


def test_interview_readiness_identifies_pending_work() -> None:
    progress = {
        "completion_rate": 40,
        "needs_review_lessons": 1,
        "lessons": [
            {"id": "lesson-1", "title": "入口", "status": "NEEDS_REVIEW"},
        ],
    }
    practice_progress = {
        "completion_rate": 33,
        "lessons": [
            {
                "lesson_id": "lesson-1",
                "lesson_title": "入口",
                "pending_tasks": ["调用链复述"],
            }
        ],
    }
    quiz_results = [{"score": 70}, {"score": 80}]
    interview_kit = {
        "core_references": [{"file": "app/main.py", "line": 1}] * 4,
        "question_mastery_rate": 25,
    }

    payload = InterviewReadinessService().build(
        progress,
        practice_progress,
        quiz_results,
        interview_kit,
    )

    assert payload["readiness_level"] == "NEEDS_WORK"
    assert payload["score_breakdown"]["quiz_average"] == 75
    assert payload["score_breakdown"]["question_rehearsal"] == 25
    assert payload["weak_lessons"][0]["title"] == "入口"
    assert payload["pending_practice_lessons"][0]["pending_tasks"] == ["调用链复述"]
    assert payload["recommended_actions"]


def test_interview_readiness_marks_ready_when_learning_loop_is_complete() -> None:
    progress = {"completion_rate": 100, "needs_review_lessons": 0, "lessons": []}
    practice_progress = {"completion_rate": 100, "lessons": []}
    quiz_results = [{"score": 90}, {"score": 95}]
    interview_kit = {
        "core_references": [{"file": "app/main.py", "line": 1}] * 8,
        "question_mastery_rate": 100,
    }

    payload = InterviewReadinessService().build(
        progress,
        practice_progress,
        quiz_results,
        interview_kit,
    )

    assert payload["readiness_score"] >= 90
    assert payload["readiness_level"] == "READY"
    assert not payload["blockers"]
