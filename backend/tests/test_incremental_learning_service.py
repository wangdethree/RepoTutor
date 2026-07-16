from __future__ import annotations

from app.services.incremental_learning_service import IncrementalLearningService


def test_incremental_learning_service_builds_follow_up_plan() -> None:
    payload = IncrementalLearningService().build(
        project={"id": "project-1", "name": "Demo"},
        impact={
            "summary": {"risk_level": "HIGH"},
            "changed_files": [{"path": "app/api/orders.py"}],
            "impacted_files": [{"path": "app/services/order_service.py"}],
            "related_routes": [{"method": "POST", "path": "/orders"}],
            "outgoing_dependencies": [{"source": "app/api/orders.py", "target": "app/services/order_service.py"}],
            "related_lessons": [
                {
                    "id": "lesson-1",
                    "title": "路由注册与请求分发",
                    "order_index": 2,
                    "matched_files": ["app/api/orders.py"],
                }
            ],
        },
        pr_review={
            "change_summary": "本次变更涉及订单路由。",
            "risk_level": "HIGH",
            "test_plan": ["补充订单接口回归测试。"],
        },
    )

    assert payload["title"] == "Demo 增量学习建议"
    assert payload["recommended_lessons"][0]["lesson_id"] == "lesson-1"
    assert len(payload["source_checkpoints"]) == 2
    assert any(task["title"] == "回归路由调用链" for task in payload["practice_tasks"])
    assert any("高风险" in question for question in payload["questions_to_ask"])
    assert payload["next_steps"]


def test_incremental_learning_service_handles_no_related_lessons() -> None:
    payload = IncrementalLearningService().build(
        project={"id": "project-1", "name": "Demo"},
        impact={
            "summary": {"risk_level": "LOW"},
            "changed_files": [{"path": "README.md"}],
            "impacted_files": [],
            "related_routes": [],
            "outgoing_dependencies": [],
            "related_lessons": [],
        },
        pr_review={
            "change_summary": "文档变更。",
            "risk_level": "LOW",
            "test_plan": [],
        },
    )

    assert payload["recommended_lessons"] == []
    assert payload["practice_tasks"][0]["title"] == "复述变更意图"
    assert payload["next_steps"] == ["先确认 diff 路径属于当前项目，再做基础静态检查。"]
