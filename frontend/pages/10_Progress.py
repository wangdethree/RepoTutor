from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")


def _status_label(status: str) -> str:
    return {
        "NOT_STARTED": "未开始",
        "IN_PROGRESS": "学习中",
        "NEEDS_REVIEW": "需复习",
        "COMPLETED": "已完成",
    }.get(status, status)


def _next_action_label(action: str) -> str:
    return {
        "PLAN_COMPLETED": "学习路线已完成",
        "REVIEW_WEAK_LESSONS": "优先复习薄弱课程",
        "CONTINUE_NEXT_LESSON": "继续下一节课程",
    }.get(action, action)


def _pending_task_label(tasks: list[str]) -> str:
    if not tasks:
        return "已完成"
    return "、".join(tasks[:2]) + ("..." if len(tasks) > 2 else "")


st.set_page_config(page_title="学习进度", page_icon="RT", layout="wide")
st.title("学习进度")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

try:
    response = requests.get(f"{API_URL}/api/projects/{project_id}/progress", timeout=30)
    response.raise_for_status()
    progress = response.json()
except requests.RequestException as exc:
    st.error(f"读取学习进度失败：{exc}")
    st.stop()

metrics = st.columns(5)
metrics[0].metric("完成率", f"{progress['completion_rate']}%")
metrics[1].metric("已完成", progress["completed_lessons"])
metrics[2].metric("学习中", progress["in_progress_lessons"])
metrics[3].metric("需复习", progress["needs_review_lessons"])
metrics[4].metric("总课程", progress["total_lessons"])

st.progress(progress["completion_rate"] / 100)
st.subheader(_next_action_label(progress["next_action"]))

next_lesson_id = progress.get("next_lesson_id")
if next_lesson_id:
    next_lesson = next((lesson for lesson in progress["lessons"] if lesson["id"] == next_lesson_id), None)
    if next_lesson:
        cols = st.columns([4, 1])
        cols[0].write(f"下一节：{next_lesson['title']}")
        if cols[1].button("继续学习", type="primary"):
            st.session_state["lesson_id"] = next_lesson_id
            st.switch_page("pages/4_Lesson_Quiz.py")

try:
    practice_response = requests.get(
        f"{API_URL}/api/projects/{project_id}/practice-progress",
        timeout=30,
    )
    practice_response.raise_for_status()
    practice_progress = practice_response.json()
except requests.RequestException as exc:
    practice_progress = None
    st.warning(f"读取动手任务进度失败：{exc}")

if practice_progress:
    st.subheader("动手任务进度")
    task_metrics = st.columns(4)
    task_metrics[0].metric("任务完成率", f"{practice_progress['completion_rate']}%")
    task_metrics[1].metric("已完成任务", practice_progress["completed_tasks"])
    task_metrics[2].metric("待完成任务", practice_progress["remaining_tasks"])
    task_metrics[3].metric("预计练习", f"{practice_progress['total_estimated_minutes']} 分钟")
    st.progress(practice_progress["completion_rate"] / 100)

    next_practice_lesson_id = practice_progress.get("next_practice_lesson_id")
    if next_practice_lesson_id:
        next_practice_lesson = next(
            (lesson for lesson in practice_progress["lessons"] if lesson["lesson_id"] == next_practice_lesson_id),
            None,
        )
        if next_practice_lesson:
            cols = st.columns([4, 1])
            cols[0].write(f"下一组任务：{next_practice_lesson['lesson_title']}")
            if cols[1].button("继续练习", key="continue-practice", type="primary"):
                st.session_state["lesson_id"] = next_practice_lesson_id
                st.switch_page("pages/4_Lesson_Quiz.py")

    st.dataframe(
        [
            {
                "序号": lesson["order_index"],
                "课程": lesson["lesson_title"],
                "状态": _status_label(lesson["status"]),
                "完成任务": f"{lesson['completed_task_count']}/{lesson['task_count']}",
                "完成率": f"{lesson['completion_rate']}%",
                "待练习": _pending_task_label(lesson["pending_tasks"]),
            }
            for lesson in practice_progress["lessons"]
        ],
        use_container_width=True,
    )

st.subheader("课程状态")
st.dataframe(
    [
        {
            "序号": lesson["order_index"],
            "课程": lesson["title"],
            "状态": _status_label(lesson["status"]),
            "最近得分": lesson["last_score"] if lesson["last_score"] is not None else "",
            "掌握度": lesson["mastery_level"],
            "更新时间": lesson["updated_at"],
        }
        for lesson in progress["lessons"]
    ],
    use_container_width=True,
)

review_lessons = [lesson for lesson in progress["lessons"] if lesson["status"] == "NEEDS_REVIEW"]
if review_lessons:
    st.subheader("待复习")
    for lesson in review_lessons:
        cols = st.columns([4, 1])
        cols[0].write(f"{lesson['order_index']}. {lesson['title']}")
        if cols[1].button("去复习", key=f"review-{lesson['id']}"):
            st.session_state["lesson_id"] = lesson["id"]
            st.switch_page("pages/4_Lesson_Quiz.py")
