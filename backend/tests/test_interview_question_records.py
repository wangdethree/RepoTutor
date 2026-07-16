from __future__ import annotations

from pathlib import Path

from app.repositories.sqlite_repository import SQLiteRepository


def test_interview_question_records_can_be_toggled(tmp_path: Path) -> None:
    repository = SQLiteRepository(f"sqlite:///{tmp_path / 'interview-question-records.db'}")
    project_id = "project-1"
    question_id = "interview-q1"

    mastered_record = repository.upsert_interview_question_record(project_id, question_id, True)
    records = repository.list_interview_question_records(project_id)
    canceled_record = repository.upsert_interview_question_record(project_id, question_id, False)

    assert mastered_record["mastered"] is True
    assert mastered_record["mastered_at"]
    assert records[0]["question_id"] == question_id
    assert records[0]["mastered"] is True
    assert canceled_record["mastered"] is False
    assert canceled_record["mastered_at"] == ""
