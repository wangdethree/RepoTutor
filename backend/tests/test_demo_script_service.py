from __future__ import annotations

from app.services.demo_script_service import DemoScriptService


def test_demo_script_builds_five_minute_project_story() -> None:
    payload = DemoScriptService().build(
        project={"id": "project-1", "name": "Demo"},
        analysis={
            "summary": {
                "project_type": "FastAPI 后端服务",
                "tech_stack": ["FastAPI", "SQLite"],
                "python_file_count": 12,
                "route_count": 5,
                "model_count": 2,
                "core_modules": ["app/main.py", "app/api/routes.py", "app/services/report.py"],
            }
        },
        plan={"lessons": [{"id": "lesson-1"}]},
        progress={
            "total_lessons": 4,
            "completed_lessons": 2,
            "needs_review_lessons": 1,
            "completion_rate": 50,
            "next_action": "REVIEW_WEAK_LESSONS",
        },
        demo_readiness={
            "readiness_score": 80,
            "ready_for_demo": True,
            "completed_items": 7,
            "total_items": 8,
            "items": [{"title": "报告导出", "status": "DONE"}],
            "next_actions": [],
        },
        improvement_suggestions={
            "suggestions": [
                {
                    "title": "补齐核心流程测试",
                    "interview_talking_point": "我会把下一步工程化重点放在测试兜底上。",
                }
            ]
        },
    )

    assert payload["title"] == "Demo 演示讲稿"
    assert payload["estimated_minutes"] == 6
    assert payload["readiness_score"] == 80
    assert len(payload["sections"]) == 6
    assert payload["sections"][0]["page"] == "pages/1_Project_Overview.py"
    assert any("测试兜底" in item for item in payload["sections"][4]["evidence"])
    assert "已经具备演示条件" in payload["closing_sentence"]
