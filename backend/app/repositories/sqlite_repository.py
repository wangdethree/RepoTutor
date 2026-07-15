from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings


class SQLiteRepository:
    """轻量 SQLite 仓储，表结构对应项目计划书中的 V1 数据模型。"""

    def __init__(self, database_url: str | None = None) -> None:
        self.database_url = database_url or settings.database_url
        self.db_path = self._sqlite_path(self.database_url)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    root_path TEXT NOT NULL,
                    project_type TEXT DEFAULT '',
                    tech_stack TEXT DEFAULT '[]',
                    analysis_status TEXT DEFAULT 'UPLOADED',
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS learner_profiles (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    python_level TEXT NOT NULL,
                    fastapi_level TEXT NOT NULL,
                    learning_goal TEXT NOT NULL,
                    daily_time TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS analysis_results (
                    project_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS diagrams (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    format TEXT NOT NULL,
                    source TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS learning_plans (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    estimated_days INTEGER NOT NULL,
                    total_lessons INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS lessons (
                    id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    order_index INTEGER NOT NULL,
                    objectives TEXT NOT NULL,
                    related_files TEXT NOT NULL,
                    estimated_minutes INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    payload TEXT DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS quizzes (
                    id TEXT PRIMARY KEY,
                    lesson_id TEXT NOT NULL,
                    questions TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS quiz_results (
                    id TEXT PRIMARY KEY,
                    quiz_id TEXT NOT NULL,
                    score INTEGER NOT NULL,
                    mastery_level TEXT NOT NULL,
                    correct_points TEXT NOT NULL,
                    missing_points TEXT NOT NULL,
                    misconceptions TEXT NOT NULL,
                    feedback TEXT NOT NULL,
                    recommended_action TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS mastery_records (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    knowledge_point TEXT NOT NULL,
                    score REAL NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS app_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS agent_runs (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    run_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    state_json TEXT NOT NULL,
                    error TEXT DEFAULT '',
                    started_at TEXT NOT NULL,
                    completed_at TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS agent_run_events (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    step_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def create_project(self, name: str, original_filename: str, root_path: Path, profile: dict[str, str]) -> dict:
        project_id = str(uuid.uuid4())
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO projects (id, name, original_filename, root_path, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (project_id, name, original_filename, str(root_path), now),
            )
            conn.execute(
                """
                INSERT INTO learner_profiles (
                    id, project_id, python_level, fastapi_level, learning_goal, daily_time, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    project_id,
                    profile["python_level"],
                    profile["fastapi_level"],
                    profile["learning_goal"],
                    profile["daily_time"],
                    now,
                ),
            )
        return self.get_project(project_id) or {}

    def list_projects(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_project(self, project_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def get_profile(self, project_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM learner_profiles WHERE project_id = ?", (project_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    def save_analysis(self, project_id: str, payload: dict) -> None:
        summary = payload["summary"]
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analysis_results (project_id, payload, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(project_id) DO UPDATE SET payload = excluded.payload, created_at = excluded.created_at
                """,
                (project_id, json.dumps(payload, ensure_ascii=False), now),
            )
            conn.execute(
                """
                UPDATE projects
                SET project_type = ?, tech_stack = ?, analysis_status = 'ANALYZED'
                WHERE id = ?
                """,
                (summary["project_type"], json.dumps(summary["tech_stack"], ensure_ascii=False), project_id),
            )

    def get_analysis(self, project_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM analysis_results WHERE project_id = ?", (project_id,)).fetchone()
        if not row:
            return None
        return json.loads(row["payload"])

    def save_diagrams(self, project_id: str, diagrams: list[dict]) -> None:
        now = self._now()
        with self._connect() as conn:
            conn.execute("DELETE FROM diagrams WHERE project_id = ?", (project_id,))
            for diagram in diagrams:
                conn.execute(
                    """
                    INSERT INTO diagrams (id, project_id, kind, title, format, source, description, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        self._diagram_storage_id(project_id, diagram["id"]),
                        project_id,
                        diagram["kind"],
                        diagram["title"],
                        diagram["format"],
                        diagram["source"],
                        diagram["description"],
                        now,
                    ),
                )

    def get_diagrams(self, project_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, kind, title, format, source, description FROM diagrams WHERE project_id = ?",
                (project_id,),
            ).fetchall()
        diagrams = [self._row_to_dict(row) for row in rows]
        for diagram in diagrams:
            diagram["id"] = self._diagram_public_id(project_id, diagram["id"])
        return diagrams

    def save_learning_plan(self, project_id: str, plan: dict) -> None:
        now = self._now()
        with self._connect() as conn:
            conn.execute("DELETE FROM learning_plans WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM lessons WHERE plan_id = ?", (plan["id"],))
            conn.execute(
                """
                INSERT INTO learning_plans (id, project_id, title, estimated_days, total_lessons, status, payload, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan["id"],
                    project_id,
                    plan["title"],
                    plan["estimated_days"],
                    plan["total_lessons"],
                    plan["status"],
                    json.dumps(plan, ensure_ascii=False),
                    now,
                ),
            )
            for lesson in plan["lessons"]:
                conn.execute(
                    """
                    INSERT INTO lessons (
                        id, plan_id, title, order_index, objectives, related_files, estimated_minutes, status, payload
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        lesson["id"],
                        plan["id"],
                        lesson["title"],
                        lesson["order_index"],
                        json.dumps(lesson["objectives"], ensure_ascii=False),
                        json.dumps(lesson["related_files"], ensure_ascii=False),
                        lesson["estimated_minutes"],
                        lesson["status"],
                        json.dumps(lesson, ensure_ascii=False),
                    ),
                )

    def get_learning_plan(self, project_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM learning_plans WHERE project_id = ?", (project_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def get_lesson(self, lesson_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    def save_lesson_payload(self, lesson_id: str, payload: dict) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE lessons SET payload = ? WHERE id = ?", (json.dumps(payload, ensure_ascii=False), lesson_id))

    def save_quiz(self, quiz: dict) -> None:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO quizzes (id, lesson_id, questions, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET questions = excluded.questions, created_at = excluded.created_at
                """,
                (quiz["id"], quiz["lesson_id"], json.dumps(quiz["questions"], ensure_ascii=False), now),
            )

    def get_quiz(self, quiz_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM quizzes WHERE id = ?", (quiz_id,)).fetchone()
        if not row:
            return None
        data = self._row_to_dict(row)
        data["questions"] = json.loads(data["questions"])
        return data

    def save_quiz_result(self, quiz_id: str, evaluation: dict) -> dict:
        result_id = str(uuid.uuid4())
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO quiz_results (
                    id, quiz_id, score, mastery_level, correct_points, missing_points,
                    misconceptions, feedback, recommended_action, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result_id,
                    quiz_id,
                    evaluation["score"],
                    evaluation["mastery_level"],
                    json.dumps(evaluation["correct_points"], ensure_ascii=False),
                    json.dumps(evaluation["missing_points"], ensure_ascii=False),
                    json.dumps(evaluation["misconceptions"], ensure_ascii=False),
                    evaluation["feedback"],
                    evaluation["recommended_action"],
                    now,
                ),
            )
        return {"id": result_id, **evaluation}

    def upsert_mastery(self, project_id: str, knowledge_point: str, score: float, status: str) -> None:
        now = self._now()
        record_id = f"{project_id}:{knowledge_point}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO mastery_records (id, project_id, knowledge_point, score, status, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE
                SET score = excluded.score, status = excluded.status, updated_at = excluded.updated_at
                """,
                (record_id, project_id, knowledge_point, score, status, now),
            )

    def get_mastery(self, project_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT knowledge_point, score, status, updated_at FROM mastery_records WHERE project_id = ?",
                (project_id,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_app_settings(self, keys: list[str]) -> dict[str, str]:
        placeholders = ",".join("?" for _ in keys)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT key, value FROM app_settings WHERE key IN ({placeholders})",
                keys,
            ).fetchall()
        return {row["key"]: row["value"] for row in rows}

    def save_app_settings(self, values: dict[str, str]) -> None:
        now = self._now()
        with self._connect() as conn:
            for key, value in values.items():
                conn.execute(
                    """
                    INSERT INTO app_settings (key, value, updated_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE
                    SET value = excluded.value, updated_at = excluded.updated_at
                    """,
                    (key, value, now),
                )

    def create_agent_run(self, project_id: str, run_type: str, initial_state: dict) -> dict:
        run_id = str(uuid.uuid4())
        now = self._now()
        payload = json.dumps(initial_state, ensure_ascii=False)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_runs (id, project_id, run_type, status, state_json, started_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (run_id, project_id, run_type, "RUNNING", payload, now),
            )
        return self.get_agent_run(run_id) or {}

    def record_agent_event(self, run_id: str, step_name: str, status: str, payload: dict) -> None:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO agent_run_events (id, run_id, step_name, status, payload_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    run_id,
                    step_name,
                    status,
                    json.dumps(payload, ensure_ascii=False),
                    now,
                ),
            )

    def finish_agent_run(self, run_id: str, status: str, state: dict, error: str = "") -> None:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE agent_runs
                SET status = ?, state_json = ?, error = ?, completed_at = ?
                WHERE id = ?
                """,
                (status, json.dumps(state, ensure_ascii=False), error, now, run_id),
            )

    def list_agent_runs(self, project_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, project_id, run_type, status, error, started_at, completed_at
                FROM agent_runs
                WHERE project_id = ?
                ORDER BY started_at DESC
                """,
                (project_id,),
            ).fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_agent_run(self, run_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        data = self._row_to_dict(row)
        data["state"] = json.loads(data.pop("state_json"))
        data["events"] = self.list_agent_run_events(run_id)
        return data

    def list_agent_run_events(self, run_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, run_id, step_name, status, payload_json, created_at
                FROM agent_run_events
                WHERE run_id = ?
                ORDER BY created_at ASC
                """,
                (run_id,),
            ).fetchall()
        events: list[dict] = []
        for row in rows:
            event = self._row_to_dict(row)
            event["payload"] = json.loads(event.pop("payload_json"))
            events.append(event)
        return events

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _sqlite_path(self, database_url: str) -> Path:
        if database_url.startswith("sqlite:///"):
            return Path(database_url.removeprefix("sqlite:///")).resolve()
        return Path(database_url).resolve()

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {key: row[key] for key in row.keys()}

    def _diagram_storage_id(self, project_id: str, diagram_id: str) -> str:
        return f"{project_id}:{diagram_id}"

    def _diagram_public_id(self, project_id: str, diagram_id: str) -> str:
        prefix = f"{project_id}:"
        return diagram_id.removeprefix(prefix)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()
