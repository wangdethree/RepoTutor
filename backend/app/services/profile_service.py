from __future__ import annotations

import json


def build_profile(
    python_level: str,
    fastapi_level: str,
    learning_goal: str,
    daily_time: str,
    learning_goals: object = None,
) -> dict:
    """归一化学习画像，兼容旧版单目标和新版多目标。"""

    goals = normalize_learning_goals(learning_goals, learning_goal)
    return {
        "python_level": str(python_level).strip() or "基础",
        "fastapi_level": str(fastapi_level).strip() or "了解基础",
        "learning_goal": "、".join(goals),
        "learning_goals": goals,
        "daily_time": str(daily_time).strip() or "30 分钟",
    }


def build_profile_from_payload(payload: dict) -> dict:
    return build_profile(
        python_level=str(payload.get("python_level", "基础")),
        fastapi_level=str(payload.get("fastapi_level", "了解基础")),
        learning_goal=str(payload.get("learning_goal", "看懂项目结构")),
        daily_time=str(payload.get("daily_time", "30 分钟")),
        learning_goals=payload.get("learning_goals"),
    )


def normalize_learning_goals(raw_goals: object, fallback_goal: str) -> list[str]:
    goals: list[str] = []
    if isinstance(raw_goals, list):
        goals = [str(goal).strip() for goal in raw_goals if str(goal).strip()]
    elif isinstance(raw_goals, str) and raw_goals.strip():
        text = raw_goals.strip()
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            decoded = None
        if isinstance(decoded, list):
            goals = [str(goal).strip() for goal in decoded if str(goal).strip()]
        else:
            goals = [item.strip() for item in text.replace(",", "、").split("、") if item.strip()]

    if not goals:
        fallback = str(fallback_goal).strip() or "看懂项目结构"
        goals = [item.strip() for item in fallback.replace(",", "、").split("、") if item.strip()]
    if not goals:
        goals = ["看懂项目结构"]
    return list(dict.fromkeys(goals))
