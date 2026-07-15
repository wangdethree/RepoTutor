from __future__ import annotations

import os
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

with tempfile.TemporaryDirectory() as temp_dir:
    os.environ["REPO_TUTOR_DATABASE_URL"] = f"sqlite:///{Path(temp_dir) / 'repotutor-e2e.db'}"
    os.environ["REPO_TUTOR_ARTIFACT_DIR"] = str(Path(temp_dir) / "artifacts")

    from fastapi.testclient import TestClient

    from app.main import app

    def main() -> None:
        """进程内端到端演示验证，不需要启动外部 HTTP 服务。"""

        client = TestClient(app)
        zip_path = _zip_demo_repository(Path(temp_dir))
        with zip_path.open("rb") as source:
            upload_response = client.post(
                "/api/projects/upload",
                data={
                    "project_name": "E2E FastAPI Shop",
                    "python_level": "基础",
                    "fastapi_level": "了解基础",
                    "learning_goal": "看懂项目结构",
                    "daily_time": "1 小时",
                },
                files={"zip_file": ("fastapi_shop.zip", source, "application/zip")},
            )
        _assert_ok(upload_response.status_code, upload_response.text)
        project_id = upload_response.json()["project"]["id"]
        print(f"project={project_id}")

        run = _json(client.post(f"/api/projects/{project_id}/agent-runs/onboarding"))
        _assert(run["status"] == "SUCCEEDED", "onboarding workflow should succeed")
        print(f"agent_run={run['id']}")

        plan = _json(client.get(f"/api/projects/{project_id}/learning-plan"))
        _assert(plan["total_lessons"] >= 7, "learning plan should contain lessons")
        lesson_id = plan["lessons"][0]["id"]
        print(f"first_lesson={lesson_id}")

        lesson = _json(client.post(f"/api/lessons/{lesson_id}/generate"))
        _assert(lesson["fact_checked"] is True, "lesson should be fact checked")
        _json(client.post(f"/api/lessons/{lesson_id}/status", json={"status": "IN_PROGRESS"}))

        question = _json(client.post(f"/api/projects/{project_id}/ask", json={"question": "登录流程经过哪些函数？"}))
        _assert(question["fact_checked"] is True, "project QA should be fact checked")
        _assert(question["references"], "project QA should include references")

        quiz = _json(client.post(f"/api/lessons/{lesson_id}/quiz"))
        answers = {
            item["id"]: "main.py app/main.py FastAPI include_router Router Service Repository Database login app/api/auth.py model schema test"
            for item in quiz["questions"]
        }
        result = _json(client.post(f"/api/quizzes/{quiz['id']}/submit", json=answers))
        _assert(result["score"] >= 80, "quiz score should complete first lesson")
        print(f"quiz_score={result['score']}")

        progress = _json(client.get(f"/api/projects/{project_id}/progress"))
        _assert(progress["completed_lessons"] >= 1, "progress should include completed lesson")
        _assert(progress["next_lesson_id"], "progress should recommend next lesson")
        print(f"progress={progress['completion_rate']}% next={progress['next_lesson_id']}")

        report = _json(client.get(f"/api/projects/{project_id}/reports/learning"))
        _assert("学习报告" in report["markdown"], "report should include markdown content")

        source = _json(client.get(f"/api/projects/{project_id}/source-files/app/main.py"))
        _assert("FastAPI" in source["content"], "source browser should return app/main.py")
        print("in-process e2e demo passed")

    def _zip_demo_repository(temp_dir: Path) -> Path:
        repo_root = ROOT / "demo_repositories" / "fastapi_shop"
        zip_path = temp_dir / "fastapi_shop.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in repo_root.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(repo_root).as_posix())
        return zip_path

    def _json(response):
        _assert_ok(response.status_code, response.text)
        return response.json()

    def _assert_ok(status_code: int, body: str) -> None:
        if status_code >= 400:
            raise AssertionError(f"HTTP {status_code}: {body}")

    def _assert(condition: bool, message: str) -> None:
        if not condition:
            raise AssertionError(message)

    if __name__ == "__main__":
        main()
