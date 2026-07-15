from __future__ import annotations

import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
API_URL = os.getenv("REPO_TUTOR_API_URL", "http://127.0.0.1:8000").rstrip("/")


def main() -> None:
    """端到端 HTTP 演示验证：需要先启动 FastAPI 后端。"""

    zip_bytes = _zip_demo_repository()
    upload = _multipart_post(
        "/api/projects/upload",
        fields={
            "project_name": "E2E FastAPI Shop",
            "python_level": "基础",
            "fastapi_level": "了解基础",
            "learning_goal": "看懂项目结构",
            "daily_time": "1 小时",
        },
        files={"zip_file": ("fastapi_shop.zip", zip_bytes, "application/zip")},
    )
    project_id = upload["project"]["id"]
    print(f"project={project_id}")

    run = _request_json("POST", f"/api/projects/{project_id}/agent-runs/onboarding")
    _assert(run["status"] == "SUCCEEDED", "onboarding workflow should succeed")
    print(f"agent_run={run['id']}")

    plan = _request_json("GET", f"/api/projects/{project_id}/learning-plan")
    _assert(plan["total_lessons"] >= 7, "learning plan should contain lessons")
    lesson_id = plan["lessons"][0]["id"]
    print(f"first_lesson={lesson_id}")

    lesson = _request_json("POST", f"/api/lessons/{lesson_id}/generate")
    _assert(lesson["fact_checked"] is True, "lesson should be fact checked")
    _request_json("POST", f"/api/lessons/{lesson_id}/status", {"status": "IN_PROGRESS"})

    quiz = _request_json("POST", f"/api/lessons/{lesson_id}/quiz")
    answers = {
        question["id"]: "main.py app/main.py FastAPI include_router Router Service Repository Database login app/api/auth.py model schema test"
        for question in quiz["questions"]
    }
    result = _request_json("POST", f"/api/quizzes/{quiz['id']}/submit", answers)
    _assert(result["score"] >= 80, "quiz score should complete first lesson")
    print(f"quiz_score={result['score']}")

    progress = _request_json("GET", f"/api/projects/{project_id}/progress")
    _assert(progress["completed_lessons"] >= 1, "progress should include completed lesson")
    _assert(progress["next_lesson_id"], "progress should recommend next lesson")
    print(f"progress={progress['completion_rate']}% next={progress['next_lesson_id']}")

    source = _request_json("GET", f"/api/projects/{project_id}/source-files/app/main.py")
    _assert("FastAPI" in source["content"], "source browser should return app/main.py")
    print("e2e demo passed")


def _zip_demo_repository() -> bytes:
    repo_root = ROOT / "demo_repositories" / "fastapi_shop"
    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = Path(temp_dir) / "fastapi_shop.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in repo_root.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(repo_root).as_posix())
        return zip_path.read_bytes()


def _request_json(method: str, path: str, payload: dict | None = None) -> dict[str, Any]:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(f"{API_URL}{path}", data=data, method=method, headers=headers)
    return _open_json(request)


def _multipart_post(path: str, fields: dict[str, str], files: dict[str, tuple[str, bytes, str]]) -> dict[str, Any]:
    boundary = f"----RepoTutorBoundary{uuid.uuid4().hex}"
    body = bytearray()
    for name, value in fields.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(value.encode("utf-8"))
        body.extend(b"\r\n")
    for name, (filename, content, content_type) in files.items():
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
        body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
        body.extend(content)
        body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())
    request = urllib.request.Request(
        f"{API_URL}{path}",
        data=bytes(body),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    return _open_json(request)


def _open_json(request: urllib.request.Request) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
