from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://127.0.0.1:8000").rstrip("/")


def main() -> None:
    checks = [
        ("root", "/"),
        ("api_health", "/api/health"),
        ("api_capabilities", "/api/capabilities"),
        ("projects", "/api/projects"),
    ]
    failures: list[str] = []
    for name, path in checks:
        try:
            status, payload = _get_json(path)
        except OSError as exc:
            failures.append(f"{name}: {exc}")
            continue
        if status >= 400:
            failures.append(f"{name}: HTTP {status}")
            continue
        print(f"{name}=ok {json.dumps(payload, ensure_ascii=False)[:180]}")

    if failures:
        print("http smoke failed")
        for failure in failures:
            print(f"- {failure}")
        raise SystemExit(1)
    print("http smoke passed")


def _get_json(path: str) -> tuple[int, dict]:
    request = urllib.request.Request(f"{API_URL}{path}", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return response.status, payload
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            payload = {"body": body}
        return exc.code, payload


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
