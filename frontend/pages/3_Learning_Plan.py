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


st.set_page_config(page_title="学习路线", page_icon="RT", layout="wide")
st.title("学习路线")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

plan = requests.get(f"{API_URL}/api/projects/{project_id}/learning-plan", timeout=60).json()
progress = requests.get(f"{API_URL}/api/projects/{project_id}/progress", timeout=60).json()
progress_by_lesson = {lesson["id"]: lesson for lesson in progress["lessons"]}

cols = st.columns(4)
cols[0].metric("课程数", plan["total_lessons"])
cols[1].metric("已完成", progress["completed_lessons"])
cols[2].metric("完成率", f"{progress['completion_rate']}%")
cols[3].metric("状态", plan["status"])

st.subheader(plan["title"])

for lesson in plan["lessons"]:
    progress_item = progress_by_lesson.get(lesson["id"], lesson)
    with st.container(border=True):
        cols = st.columns([1, 4, 2, 2, 2])
        cols[0].markdown(f"### {lesson['order_index']}")
        cols[1].markdown(f"**{lesson['title']}**")
        cols[1].write("目标：" + "；".join(lesson["objectives"]))
        cols[1].caption("相关文件：" + "、".join(lesson["related_files"] or ["待从核心模块阅读"]))
        cols[2].write(_status_label(progress_item.get("status", "NOT_STARTED")))
        if progress_item.get("last_score") is not None:
            cols[2].caption(f"最近得分：{progress_item['last_score']}")
        cols[3].write(f"{lesson['estimated_minutes']} 分钟")
        cols[3].caption("前置：" + "、".join(lesson["prerequisites"]))
        if cols[4].button("进入课程", key=lesson["id"]):
            st.session_state["lesson_id"] = lesson["id"]
            st.switch_page("pages/4_Lesson_Quiz.py")
