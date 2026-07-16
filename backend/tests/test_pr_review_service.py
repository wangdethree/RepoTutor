from __future__ import annotations

from app.services.pr_review_service import PRReviewService


def test_pr_review_service_builds_review_pack_from_impact() -> None:
    payload = PRReviewService().build(
        project={"id": "project-1", "name": "Demo"},
        diff_text="""diff --git a/app/api/orders.py b/app/api/orders.py
--- a/app/api/orders.py
+++ b/app/api/orders.py
@@ -1,2 +1,3 @@
+include_coupon = True
-old_flag = False
""",
        impact={
            "summary": {
                "changed_file_count": 1,
                "unknown_changed_file_count": 0,
                "impacted_file_count": 2,
                "risk_level": "MEDIUM",
            },
            "changed_files": [{"path": "app/api/orders.py"}],
            "impacted_files": [{"path": "app/services/order_service.py"}],
            "related_routes": [{"method": "POST", "path": "/orders"}],
            "related_lessons": [
                {
                    "id": "lesson-1",
                    "title": "路由注册与请求分发",
                    "order_index": 2,
                    "matched_files": ["app/api/orders.py"],
                }
            ],
        },
    )

    assert payload["title"] == "Demo PR 讲解包"
    assert payload["risk_level"] == "MEDIUM"
    assert payload["line_stats"]["additions"] == 1
    assert payload["line_stats"]["deletions"] == 1
    assert payload["affected_surface"]["routes"] == ["POST /orders"]
    assert payload["learning_impacts"][0]["lesson_id"] == "lesson-1"
    assert any(item["status"] == "NEEDS_CHECK" for item in payload["review_checklist"])
    assert payload["test_plan"]
    assert payload["interview_talking_points"]


def test_pr_review_service_handles_unknown_low_context_diff() -> None:
    payload = PRReviewService().build(
        project={"id": "project-1", "name": "Demo"},
        diff_text="""diff --git a/docs/readme.md b/docs/readme.md
--- a/docs/readme.md
+++ b/docs/readme.md
@@ -1 +1 @@
-old
+new
""",
        impact={
            "summary": {
                "changed_file_count": 1,
                "unknown_changed_file_count": 1,
                "impacted_file_count": 0,
                "risk_level": "LOW",
            },
            "changed_files": [{"path": "docs/readme.md"}],
            "impacted_files": [],
            "related_routes": [],
            "related_lessons": [],
        },
    )

    assert "未知文件" in payload["merge_advice"]
    assert payload["review_checklist"][0]["status"] == "NEEDS_CHECK"
