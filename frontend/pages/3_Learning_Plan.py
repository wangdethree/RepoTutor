from __future__ import annotations

import os

import requests
import streamlit as st


API_URL = os.getenv("REPO_TUTOR_API_URL", "http://localhost:8000")

st.set_page_config(page_title="学习路线", page_icon="RT", layout="wide")
st.title("学习路线")

project_id = st.session_state.get("project_id")
if not project_id:
    st.info("请先在首页上传或选择项目。")
    st.stop()

plan = requests.get(f"{API_URL}/api/projects/{project_id}/learning-plan", timeout=60).json()

cols = st.columns(3)
cols[0].metric("课程数", plan["total_lessons"])
cols[1].metric("预计天数", plan["estimated_days"])
cols[2].metric("状态", plan["status"])

st.subheader(plan["title"])

for lesson in plan["lessons"]:
    with st.container(border=True):
        cols = st.columns([1, 4, 2, 2])
        cols[0].markdown(f"### {lesson['order_index']}")
        cols[1].markdown(f"**{lesson['title']}**")
        cols[1].write("目标：" + "；".join(lesson["objectives"]))
        cols[1].caption("相关文件：" + "、".join(lesson["related_files"] or ["待从核心模块阅读"]))
        cols[2].write(f"{lesson['estimated_minutes']} 分钟")
        cols[2].caption("前置：" + "、".join(lesson["prerequisites"]))
        if cols[3].button("进入课程", key=lesson["id"]):
            st.session_state["lesson_id"] = lesson["id"]
            st.switch_page("pages/4_Lesson_Quiz.py")

